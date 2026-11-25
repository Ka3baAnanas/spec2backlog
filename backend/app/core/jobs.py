import logging
import threading
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.events import emit
from app.domain.models import Project
from app.modules.generation.service import run_generation

logger = logging.getLogger(__name__)

_runs: dict[str, dict] = {}
_lock = threading.Lock()


def _new_record(project_id: str, only_failed: bool, resume: bool, backend: str) -> dict:
    return {
        "run_id": uuid.uuid4().hex,
        "project_id": project_id,
        "kind": "generation",
        "only_failed": only_failed,
        "resume": resume,
        "backend": backend,
        "status": "running",
        "started_at": datetime.now(UTC).isoformat(),
        "finished_at": None,
    }


def _start_thread(record: dict) -> None:
    thread = threading.Thread(
        target=_run,
        args=(
            record["project_id"],
            record["only_failed"],
            record["run_id"],
            record["resume"],
        ),
        name=f"generate-{record['project_id'][:8]}-{record['run_id'][:8]}",
        daemon=True,
    )
    thread.start()


def start_generation(project_id: str, *, only_failed: bool = False, resume: bool = False) -> dict:
    if settings.use_celery:
        from app.core.tasks import generate_project_task

        record = _new_record(project_id, only_failed, resume, "celery")
        try:
            generate_project_task.apply_async(
                args=(project_id, record["run_id"], only_failed, resume),
                task_id=record["run_id"],
                queue=settings.celery_queue,
            )
        except Exception as exc:  # noqa: BLE001 - broker outages must fall back
            logger.warning("Celery unavailable; using in-process runner: %s", exc)
            emit(
                project_id,
                "generation",
                "warning",
                "Celery unavailable; running generation in-process",
                {"reason": f"{type(exc).__name__}: {exc}", "run_id": record["run_id"]},
            )
            record["backend"] = "in-process"
            with _lock:
                _runs[project_id] = record
            _start_thread(record)
    else:
        record = _new_record(project_id, only_failed, resume, "in-process")
        with _lock:
            _runs[project_id] = record
        _start_thread(record)

    return {
        "run_id": record["run_id"],
        "status": "running",
        "only_failed": only_failed,
        "resume": resume,
        "backend": record["backend"],
    }


def _run(project_id: str, only_failed: bool, run_id: str, resume: bool = False) -> None:
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if not project:
            emit(project_id, "generation", "error", "Project not found", {"run_id": run_id})
            return
        run_generation(db, project, only_failed=only_failed, run_id=run_id, resume=resume)
    except Exception as exc:
        db.rollback()
        logger.exception("generation job %s failed", run_id)
        project = db.get(Project, project_id)
        if project:
            project.status = "failed"
            project.error = f"{type(exc).__name__}: {exc}"
            db.commit()
        emit(
            project_id,
            "generation",
            "error",
            f"Generation failed: {type(exc).__name__}: {exc}",
            {"run_id": run_id, "error": str(exc)},
        )
    finally:
        with _lock:
            record = _runs.get(project_id)
            if record and record["run_id"] == run_id:
                record["status"] = "finished"
                record["finished_at"] = datetime.now(UTC).isoformat()
        db.close()


def get_run(project_id: str) -> dict | None:
    with _lock:
        record = dict(_runs[project_id]) if project_id in _runs else None
    if not record:
        return None

    if record.get("backend") == "celery":
        try:
            from app.core.celery_app import celery_app

            result = celery_app.AsyncResult(record["run_id"])
            state = result.state
            status = {
                "PENDING": "queued",
                "RECEIVED": "queued",
                "STARTED": "running",
                "RETRY": "running",
                "SUCCESS": "finished",
                "FAILURE": "failed",
            }.get(state, "running")
            record["status"] = status
            record["celery_state"] = state
            if state == "RETRY":
                record["retries"] = int(getattr(result, "retries", 0) or 0)
            if state == "FAILURE":
                record["error"] = str(result.info)
            elif isinstance(result.info, dict):
                if result.info.get("status") == "failed":
                    record["error"] = result.info.get("error")
                record["result"] = result.info
            with _lock:
                current = _runs.get(project_id)
                if current and current["run_id"] == record["run_id"]:
                    current.update(record)
        except Exception as exc:  # noqa: BLE001 - state polling is best-effort
            logger.debug("could not read Celery state for run %s: %s", record["run_id"], exc)

    return record


def _celery_project_is_running(project_id: str) -> bool:
    try:
        from app.core.celery_app import celery_app

        inspection = celery_app.control.inspect(timeout=1)
        groups = [
            inspection.active() or {},
            inspection.reserved() or {},
            inspection.scheduled() or {},
        ]
        for group in groups:
            for tasks in group.values():
                for task in tasks or []:
                    request = task.get("request") or task
                    if request.get("name") != "generation.generate_project":
                        continue
                    args = request.get("args") or []
                    if args and args[0] == project_id:
                        return True
    except Exception as exc:  # noqa: BLE001 - inspection is best-effort
        logger.debug("could not inspect Celery workers: %s", exc)
    return False


def recover_stale_runs() -> list[str]:
    db = SessionLocal()
    try:
        projects = db.scalars(select(Project).where(Project.status == "generating")).all()
    finally:
        db.close()

    recovered: list[str] = []
    for project in projects:
        run = get_run(project.id)
        if run and run.get("status") in ("running", "queued"):
            continue
        if settings.use_celery and _celery_project_is_running(project.id):
            continue
        emit(
            project.id,
            "generation",
            "warning",
            "Generation was interrupted by a restart; resuming pending sections",
            {"resume": True},
        )
        start_generation(project.id, resume=True)
        recovered.append(project.id)
    return recovered
