"""Generation orchestration: requirement leaves -> generator -> consolidator -> quality."""

import time

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.events import emit
from app.domain.models import BacklogItem, GenerationTrace, Project, Question, Section
from app.modules.generation.consolidator import consolidate
from app.modules.generation.generator import GenerationResult, generate_for_section
from app.modules.generation.quality import score_project
from app.modules.generation.schema import empty_counts
from app.providers.errors import (
    is_retryable_message,
    is_retryable_provider_error,
    retryable_message,
)
from app.providers.factory import get_llm, provider_info


def _requirement_sections(db: Session, project_id: str) -> list[Section]:
    return list(
        db.scalars(
            select(Section)
            .where(
                Section.project_id == project_id,
                Section.role == "requirement",
                Section.is_leaf.is_(True),
            )
            .order_by(Section.position)
        ).all()
    )


def _latest_status_by_section(db: Session, project_id: str) -> dict[str, str]:
    traces = db.scalars(
        select(GenerationTrace)
        .where(GenerationTrace.project_id == project_id)
        .order_by(GenerationTrace.id)
    ).all()
    return {trace.section_id: trace.status for trace in traces}


def _result_from_trace(trace: GenerationTrace) -> GenerationResult:
    return GenerationResult(
        section_id=trace.section_id,
        status=trace.status,
        output=trace.response_json,
        error=trace.error,
        attempts=trace.attempts or 0,
        duration_ms=trace.duration_ms or 0,
        trace_id=trace.id,
        counts=trace.items_created or {},
        retryable=is_retryable_message(trace.error),
    )


def _clear_backlog(db: Session, project_id: str, section_ids: list[str] | None = None) -> None:
    item_query = db.query(BacklogItem).filter(BacklogItem.project_id == project_id)
    question_query = db.query(Question).filter(Question.project_id == project_id)
    if section_ids is not None:
        item_query = item_query.filter(BacklogItem.source_section_id.in_(section_ids))
        question_query = question_query.filter(Question.section_id.in_(section_ids))
    item_query.delete(synchronize_session=False)
    question_query.delete(synchronize_session=False)
    db.flush()


def _retry_countdown(retry_count: int) -> float:
    delay = settings.celery_retry_backoff_seconds * (2 ** retry_count)
    return min(settings.celery_retry_max_backoff_seconds, delay)


def _base_payload(
    *,
    project_id: str,
    run_id: str | None,
    leaves: int,
    succeeded: int,
    failed: int,
    only_failed: bool,
    resume: bool,
    retryable_failed: int = 0,
) -> dict:
    return {
        "project_id": project_id,
        "run_id": run_id,
        "leaves": leaves,
        "succeeded": succeeded,
        "failed": failed,
        "retryable_failed": retryable_failed,
        "only_failed": only_failed,
        "resume": resume,
    }


def _finish_retry(
    db: Session,
    project: Project,
    payload: dict,
    *,
    error: str,
    retry_count: int,
) -> dict:
    countdown = _retry_countdown(retry_count)
    project.status = "generating"
    project.error = None
    db.commit()
    emit(
        project.id,
        "generation",
        "warning",
        f"Generation paused; retrying in {countdown:.0f}s from saved traces",
        {
            **payload,
            "status": "retry_pending",
            "retry_requested": True,
            "retry_in": countdown,
            "error": error,
        },
    )
    return {
        **payload,
        **empty_counts(),
        "status": "retry_pending",
        "retry_requested": True,
        "retry_in": countdown,
        "error": error,
    }


def _finish_failed(
    db: Session,
    project: Project,
    payload: dict,
    *,
    error: str,
    counts: dict | None = None,
) -> dict:
    project.status = "failed"
    project.error = error
    db.commit()
    result = {
        **payload,
        **(counts or empty_counts()),
        "status": "failed",
        "error": error,
    }
    emit(
        project.id,
        "generation",
        "stage_end",
        f"Generation stopped: {error}",
        result,
    )
    return result


def run_generation(
    db: Session,
    project: Project,
    *,
    only_failed: bool = False,
    run_id: str | None = None,
    resume: bool = False,
    celery_retry_count: int = 0,
) -> dict:
    project_id = project.id
    project.status = "generating"
    project.error = None
    db.commit()

    info = provider_info()
    emit(
        project_id,
        "generation",
        "info",
        f"Provider {info['llm']['active']} model {info['llm']['model']}",
        {"llm": info["llm"], "embeddings": info["embeddings"], "run_id": run_id},
    )
    if info["offline_demo"]:
        emit(project_id, "generation", "warning", info["message"],
             {"llm": info["llm"], "embeddings": info["embeddings"], "run_id": run_id,
              "demo_mode": True})

    all_leaves = _requirement_sections(db, project_id)
    leaves = list(all_leaves)
    reused: list[GenerationResult] = []
    if only_failed:
        latest = _latest_status_by_section(db, project_id)
        leaves = [leaf for leaf in leaves if latest.get(leaf.id) == "failed"]
    elif resume:
        traces = db.scalars(
            select(GenerationTrace)
            .where(GenerationTrace.project_id == project_id)
            .order_by(GenerationTrace.id)
        ).all()
        latest = _latest_status_by_section(db, project_id)
        completed = {
            section_id
            for section_id, status in latest.items()
            if status in ("ok", "retried")
        }
        leaf_ids = {leaf.id for leaf in leaves}
        reused = [
            _result_from_trace(trace)
            for trace in traces
            if trace.section_id in completed and trace.section_id in leaf_ids
        ]
        leaves = [leaf for leaf in leaves if leaf.id not in completed]
        emit(
            project_id,
            "generation",
            "info",
            f"Resuming {len(leaves)} pending section(s), reusing {len(reused)} completed result(s)",
            {"resume": True, "reused": len(reused), "run_id": run_id},
        )

    total = len(leaves)
    emit(project_id, "generation", "stage_start",
         f"Generating backlog for {total} requirement section(s)",
         {"N": total, "only_failed": only_failed, "resume": resume, "run_id": run_id})

    base = _base_payload(
        project_id=project_id,
        run_id=run_id,
        leaves=len(all_leaves),
        succeeded=0,
        failed=0,
        only_failed=only_failed,
        resume=resume,
    )
    can_retry = settings.use_celery and celery_retry_count < settings.celery_task_max_retries

    try:
        llm = get_llm()
    except Exception as exc:  # noqa: BLE001 - invalid configuration must be visible
        error = f"Provider configuration failed: {type(exc).__name__}: {exc}"
        return _finish_failed(db, project, base, error=error)

    results: list[GenerationResult] = list(reused)
    failed_results: list[GenerationResult] = []
    for index, leaf in enumerate(leaves, 1):
        emit(project_id, "generation", "leaf_start",
             f"Section {index}/{total}: {leaf.number or leaf.title}",
             {"section_id": leaf.id, "i": index, "N": total})
        if settings.demo_delay_ms > 0:
            time.sleep(settings.demo_delay_ms / 1000.0)
        result = generate_for_section(db, project, leaf, llm=llm)
        if result.status == "failed":
            failed_results.append(result)
            emit(project_id, "generation", "leaf_failed",
                 f"Section failed after {result.attempts} attempt(s): {result.error}",
                 {"section_id": leaf.id, "error": result.error,
                  "attempts": result.attempts, "retryable": result.retryable})
        else:
            results.append(result)
            emit(project_id, "generation", "leaf_done",
                 f"Section done: {result.counts['stories']} stories",
                 {"section_id": leaf.id, **result.counts,
                  "duration_ms": result.duration_ms, "attempts": result.attempts})

    failed = len(failed_results)
    retryable_failed = sum(
        1 for result in failed_results
        if result.retryable or is_retryable_message(result.error)
    )
    base.update(
        succeeded=len(results),
        failed=failed,
        retryable_failed=retryable_failed,
    )

    if failed:
        first_error = failed_results[0].error or "unknown provider failure"
        error = f"{failed} requirement section(s) failed: {first_error}"
        if retryable_failed:
            error = retryable_message(error)
        if retryable_failed == failed and can_retry:
            return _finish_retry(
                db, project, base, error=error, retry_count=celery_retry_count
            )
        return _finish_failed(db, project, base, error=error)

    if only_failed:
        _clear_backlog(db, project_id, [result.section_id for result in results])
    else:
        _clear_backlog(db, project_id)
    db.commit()

    emit(
        project_id,
        "generation",
        "progress",
        f"Consolidating {len(results)} section result(s) into a coherent backlog",
        {"sections": len(results), "run_id": run_id},
    )

    def on_consolidation_event(kind: str, message: str, data: dict) -> None:
        emit(project_id, "generation", kind, message, data)

    try:
        counts = consolidate(
            db, project, results, llm=llm, on_event=on_consolidation_event
        )
    except Exception as exc:  # noqa: BLE001 - consolidation must not publish partial output
        retryable = is_retryable_provider_error(exc) or is_retryable_message(str(exc))
        error = f"Consolidation failed: {type(exc).__name__}: {exc}"
        if retryable:
            error = retryable_message(error)
        if retryable and can_retry:
            return _finish_retry(
                db, project, base, error=error, retry_count=celery_retry_count
            )
        return _finish_failed(db, project, base, error=error)

    quality = score_project(db, project_id)
    existing_items = db.scalar(
        select(func.count(BacklogItem.id)).where(BacklogItem.project_id == project_id)
    )
    requirement_total = len(all_leaves)
    if requirement_total == 0 and not results:
        return _finish_failed(
            db,
            project,
            base,
            error="No requirement section found. Check the document structure and roles.",
            counts=counts,
        )
    if not results:
        return _finish_failed(
            db,
            project,
            base,
            error=f"All {requirement_total} requirement section(s) failed during generation.",
            counts=counts,
        )

    project.status = "generated"
    project.error = None
    db.commit()

    payload = {
        **base,
        **counts,
        "status": "generated",
        "quality": quality,
        "existing_items": existing_items or 0,
    }
    emit(
        project_id,
        "generation",
        "stage_end",
        f"Generation finished: {counts['stories']} stories across {counts['epics']} epics",
        payload,
    )
    return payload
