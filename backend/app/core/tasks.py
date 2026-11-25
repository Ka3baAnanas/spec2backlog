from celery.exceptions import Retry
from sqlalchemy.exc import InterfaceError, OperationalError

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.db import SessionLocal
from app.core.events import emit
from app.domain.models import Project
from app.modules.generation.service import run_generation
from app.providers.errors import ProviderUnavailableError


def _retry_countdown(retry_count: int) -> float:
    delay = settings.celery_retry_backoff_seconds * (2 ** retry_count)
    return min(settings.celery_retry_max_backoff_seconds, delay)


@celery_app.task(
    bind=True,
    name="generation.generate_project",
    max_retries=settings.celery_task_max_retries,
    acks_late=True,
)
def generate_project_task(self, project_id: str, run_id: str, only_failed: bool = False, resume: bool = False):
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if not project:
            emit(
                project_id,
                "generation",
                "error",
                "Project not found",
                {"run_id": run_id},
            )
            return {"status": "failed", "error": "project not found", "run_id": run_id}

        result = run_generation(
            db,
            project,
            only_failed=only_failed,
            run_id=run_id,
            resume=resume,
            celery_retry_count=self.request.retries,
        )
        if result.get("retry_requested"):
            if self.request.retries >= settings.celery_task_max_retries:
                return {"status": "failed", "run_id": run_id, **result}
            countdown = float(result.get("retry_in") or _retry_countdown(self.request.retries))
            raise self.retry(
                args=(project_id, run_id, False, True),
                exc=ProviderUnavailableError(result.get("error", "provider unavailable")),
                countdown=countdown,
            )
        return {"run_id": run_id, **result}
    except Retry:
        raise
    except (OperationalError, InterfaceError) as exc:
        db.rollback()
        countdown = _retry_countdown(self.request.retries)
        raise self.retry(
            args=(project_id, run_id, False, True),
            exc=exc,
            countdown=countdown,
        )
    except Exception as exc:  # noqa: BLE001 - generation errors must be journaled
        db.rollback()
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
        return {"status": "failed", "run_id": run_id, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        db.close()
