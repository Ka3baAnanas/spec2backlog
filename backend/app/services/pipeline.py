"""Background pipeline orchestration (thread-based, no external broker needed)."""
import logging
import threading
import uuid

from app.core.db import SessionLocal
from app.models import Project
from app.services.events import emit
from app.services.generation.runner import generate_project
from app.services.graph.builder import build_graph_for_project

logger = logging.getLogger(__name__)

ALLOWED_STAGES = ("graph", "generate")


def start_pipeline(project_id: str, stages: list[str]) -> dict:
    run_id = uuid.uuid4().hex
    thread = threading.Thread(
        target=_run,
        args=(project_id, stages, run_id),
        name=f"pipeline-{project_id[:8]}-{run_id[:8]}",
        daemon=True,
    )
    thread.start()
    return {"run_id": run_id}


def _run(project_id: str, stages: list[str], run_id: str) -> None:
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if not project:
            emit(project_id, "graph", "error", "Project not found", {"run_id": run_id})
            return
        for stage in stages:
            try:
                if stage == "graph":
                    build_graph_for_project(db, project)
                elif stage == "generate":
                    generate_project(db, project)
            except Exception as exc:
                db.rollback()
                logger.exception("pipeline stage %s failed", stage)
                emit(project_id, stage, "error",
                     f"{stage} stage failed: {type(exc).__name__}: {exc}",
                     {"run_id": run_id, "error": str(exc)})
                break
    finally:
        db.close()
