"""In-process background runner for generation jobs."""

import logging
import threading
import uuid
from datetime import UTC, datetime

from app.core.db import SessionLocal
from app.core.events import emit
from app.domain.models import Project
from app.modules.generation.service import run_generation

logger = logging.getLogger(__name__)

_runs: dict[str, dict] = {}
_lock = threading.Lock()


def start_generation(project_id: str, *, only_failed: bool = False) -> dict:
    run_id = uuid.uuid4().hex
    record = {
        "run_id": run_id,
        "project_id": project_id,
        "kind": "generation",
        "only_failed": only_failed,
        "status": "running",
        "started_at": datetime.now(UTC).isoformat(),
        "finished_at": None,
    }
    with _lock:
        _runs[project_id] = record
    thread = threading.Thread(
        target=_run,
        args=(project_id, only_failed, run_id),
        name=f"generate-{project_id[:8]}-{run_id[:8]}",
        daemon=True,
    )
    thread.start()
    return {"run_id": run_id, "status": "running", "only_failed": only_failed}


def _run(project_id: str, only_failed: bool, run_id: str) -> None:
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if not project:
            emit(project_id, "generation", "error", "Project not found", {"run_id": run_id})
            return
        run_generation(db, project, only_failed=only_failed, run_id=run_id)
    except Exception as exc:
        db.rollback()
        logger.exception("generation job %s failed", run_id)
        project = db.get(Project, project_id)
        if project:
            project.status = "failed"
            project.error = f"{type(exc).__name__}: {exc}"
            db.commit()
        emit(project_id, "generation", "error",
             f"Generation failed: {type(exc).__name__}: {exc}",
             {"run_id": run_id, "error": str(exc)})
    finally:
        with _lock:
            record = _runs.get(project_id)
            if record and record["run_id"] == run_id:
                record["status"] = "finished"
                record["finished_at"] = datetime.now(UTC).isoformat()
        db.close()


def get_run(project_id: str) -> dict | None:
    with _lock:
        record = _runs.get(project_id)
        return dict(record) if record else None
