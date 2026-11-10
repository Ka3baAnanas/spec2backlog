"""Generation orchestration: requirement leaves -> generator -> consolidator -> quality."""

import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.events import emit
from app.domain.models import BacklogItem, GenerationTrace, Project, Question, Section
from app.modules.generation.consolidator import consolidate
from app.modules.generation.generator import GenerationResult, generate_for_section
from app.modules.generation.quality import score_project
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


def _clear_backlog(db: Session, project_id: str, section_ids: list[str] | None = None) -> None:
    item_query = db.query(BacklogItem).filter(BacklogItem.project_id == project_id)
    question_query = db.query(Question).filter(Question.project_id == project_id)
    if section_ids is not None:
        item_query = item_query.filter(BacklogItem.source_section_id.in_(section_ids))
        question_query = question_query.filter(Question.section_id.in_(section_ids))
    item_query.delete(synchronize_session=False)
    question_query.delete(synchronize_session=False)
    db.flush()


def run_generation(
    db: Session, project: Project, *, only_failed: bool = False, run_id: str | None = None
) -> dict:
    project_id = project.id
    project.status = "generating"
    project.error = None
    db.commit()

    info = provider_info()
    if info["offline_demo"]:
        emit(project_id, "generation", "warning", info["message"],
             {"llm": info["llm"], "embeddings": info["embeddings"], "run_id": run_id})

    leaves = _requirement_sections(db, project_id)
    if only_failed:
        latest = _latest_status_by_section(db, project_id)
        leaves = [leaf for leaf in leaves if latest.get(leaf.id) == "failed"]

    total = len(leaves)
    emit(project_id, "generation", "stage_start",
         f"Generating backlog for {total} requirement section(s)",
         {"N": total, "only_failed": only_failed, "run_id": run_id})

    llm = get_llm()
    results: list[GenerationResult] = []
    failed = 0
    for index, leaf in enumerate(leaves, 1):
        emit(project_id, "generation", "leaf_start",
             f"Section {index}/{total}: {leaf.number or leaf.title}",
             {"section_id": leaf.id, "i": index, "N": total})
        if settings.demo_delay_ms > 0:
            time.sleep(settings.demo_delay_ms / 1000.0)
        result = generate_for_section(db, project, leaf, llm=llm)
        if result.status == "failed":
            failed += 1
            emit(project_id, "generation", "leaf_failed",
                 f"Section failed after {result.attempts} attempt(s): {result.error}",
                 {"section_id": leaf.id, "error": result.error, "attempts": result.attempts})
        else:
            results.append(result)
            emit(project_id, "generation", "leaf_done",
                 f"Section done: {result.counts['stories']} stories",
                 {"section_id": leaf.id, **result.counts,
                  "duration_ms": result.duration_ms, "attempts": result.attempts})

    if only_failed:
        _clear_backlog(db, project_id, [result.section_id for result in results])
    else:
        _clear_backlog(db, project_id)

    counts = consolidate(db, project, results)
    quality = score_project(db, project_id)

    existing_items = db.query(BacklogItem).filter(BacklogItem.project_id == project_id).count()
    if total == 0:
        project.status = "failed"
        project.error = "No requirement section found. Check the document structure and roles."
    elif failed == total:
        project.status = "failed"
        project.error = f"All {total} requirement section(s) failed during generation."
    else:
        project.status = "generated"
        project.error = None
    db.commit()

    payload = {
        **counts,
        "quality": quality,
        "leaves": total,
        "succeeded": total - failed,
        "failed": failed,
        "only_failed": only_failed,
        "run_id": run_id,
        "existing_items": existing_items,
    }
    emit(project_id, "generation", "stage_end",
         f"Generation finished: {counts['stories']} stories, {failed} failed section(s)",
         payload)
    return payload
