"""One LLM call per requirement leaf: exact context, JSON validation, one retry, trace."""

import time
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.events import emit
from app.domain.models import GenerationTrace, Project, Section
from app.modules.context.builder import build_prompt
from app.modules.generation.prompts import load_template
from app.modules.generation.schema import empty_counts, output_json_schema, validate_output
from app.providers.errors import is_retryable_provider_error, retryable_message
from app.providers.factory import get_llm


@dataclass
class GenerationResult:
    section_id: str
    status: str
    output: dict | None = None
    error: str | None = None
    attempts: int = 0
    duration_ms: int = 0
    trace_id: int | None = None
    counts: dict = field(default_factory=empty_counts)
    retryable: bool = False


def _clean_text(value):
    """Remove em dashes and double dashes from generated text."""
    if isinstance(value, str):
        return value.replace("—", ",").replace("--", ",")
    if isinstance(value, list):
        return [_clean_text(item) for item in value]
    if isinstance(value, dict):
        return {key: _clean_text(item) for key, item in value.items()}
    return value


def _counts(output: dict) -> dict:
    stories = output.get("stories") or []
    return {
        "epics": 0,
        "features": 0,
        "stories": len(stories),
        "tests": sum(len(story.get("tests") or []) for story in stories),
        "questions": len(output.get("questions") or []),
    }


def generate_for_section(
    db: Session,
    project: Project,
    section: Section,
    *,
    instruction: str | None = None,
    llm=None,
) -> GenerationResult:
    """Generate one section. Never raises on provider/validation errors; records a trace."""
    llm = llm or get_llm()
    prompt, context = build_prompt(db, section, instruction=instruction)
    system = load_template("system")
    schema = output_json_schema()

    def on_event(kind: str, message: str, data: dict) -> None:
        emit(
            project.id,
            "generation",
            kind,
            message,
            {"section_id": section.id, "section_number": section.number, **data},
        )

    started = time.perf_counter()
    attempts = 0
    output = None
    first_exc: Exception | None = None
    retryable = False
    status = "ok"
    while attempts < 2:  # one automatic retry
        attempts += 1
        try:
            try:
                raw = llm.complete_json(system, prompt, schema, on_event=on_event)
            except TypeError as exc:
                if "on_event" not in str(exc):
                    raise
                raw = llm.complete_json(system, prompt, schema)
            output = _clean_text(validate_output(raw))
            status = "retried" if attempts > 1 else "ok"
            break
        except Exception as exc:  # noqa: BLE001 - provider errors must be retried/isolated
            if first_exc is None:
                first_exc = exc
            retryable = retryable or is_retryable_provider_error(exc)
            output = None
            status = "failed"

    first_error = f"{type(first_exc).__name__}: {first_exc}" if first_exc else None
    if first_error and status == "failed" and retryable:
        first_error = retryable_message(first_error)
    duration_ms = int((time.perf_counter() - started) * 1000)
    counts = _counts(output) if output else empty_counts()
    trace = GenerationTrace(
        project_id=project.id,
        section_id=section.id,
        prompt=prompt,
        response_json=output,
        links=context.get("links", []),
        global_context_ids=[item["section_id"] for item in context.get("global_context", [])],
        duration_ms=duration_ms,
        attempts=attempts,
        status=status,
        error=first_error if status in ("failed", "retried") else None,
        items_created=counts,
    )
    db.add(trace)
    db.commit()
    db.refresh(trace)
    return GenerationResult(
        section_id=section.id,
        status=status,
        output=output,
        error=trace.error,
        attempts=attempts,
        duration_ms=duration_ms,
        trace_id=trace.id,
        counts=counts,
        retryable=retryable and status == "failed",
    )
