"""Pipeline event journal.

Every emit() uses its own short-lived session so background threads can write
progress even while the request/run session is busy. Failures to write an event
must never break the pipeline.
"""
import logging
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import RunEvent

logger = logging.getLogger(__name__)

STAGES = ("ingestion", "tree", "graph", "generation", "export")
EVENT_TYPES = (
    "stage_start", "stage_end", "progress", "leaf_start", "leaf_done",
    "leaf_failed", "link_found", "warning", "error",
)


def emit(
    project_id: str,
    stage: str,
    type: str,
    message: str = "",
    data: dict | None = None,
) -> int | None:
    """Append one RunEvent in its own session. Returns the event id (or None on failure)."""
    db = SessionLocal()
    try:
        ev = RunEvent(
            project_id=project_id,
            ts=datetime.now(UTC).replace(tzinfo=None),
            stage=stage,
            type=type,
            message=message or "",
            data=data or {},
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)
        return ev.id
    except Exception:  # never let observability break the pipeline
        db.rollback()
        logger.exception("could not persist %s/%s event for project %s", stage, type, project_id)
        return None
    finally:
        db.close()


def event_to_dict(ev: RunEvent) -> dict:
    return {
        "id": ev.id,
        "project_id": ev.project_id,
        "ts": ev.ts.isoformat() if ev.ts else None,
        "stage": ev.stage,
        "type": ev.type,
        "message": ev.message or "",
        "data": ev.data or {},
    }


def fetch_events(project_id: str, after: int = 0, limit: int = 1000) -> list[dict]:
    """Read events after an id using its own short session (safe from async/threads)."""
    db = SessionLocal()
    try:
        rows = db.scalars(
            select(RunEvent)
            .where(RunEvent.project_id == project_id, RunEvent.id > max(after, 0))
            .order_by(RunEvent.id)
            .limit(limit)
        ).all()
        return [event_to_dict(e) for e in rows]
    finally:
        db.close()
