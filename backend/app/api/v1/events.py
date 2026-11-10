import asyncio
import json
import time

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.db import SessionLocal, get_db
from app.core.events import fetch_events
from app.domain.models import Project

router = APIRouter(prefix="/api/v1", tags=["events"])


@router.get("/projects/{project_id}/events/history")
def events_history(
    project_id: str,
    after: int = 0,
    limit: int = Query(1000, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    if not db.get(Project, project_id):
        raise HTTPException(404, "project not found")
    return fetch_events(project_id, after=after, limit=limit)


@router.get("/projects/{project_id}/events")
async def stream_events(
    project_id: str,
    request: Request,
    last_event_id: str | None = None,
):
    def _exists() -> bool:
        with SessionLocal() as session:
            return session.get(Project, project_id) is not None

    if not await run_in_threadpool(_exists):
        raise HTTPException(404, "project not found")

    header_id = request.headers.get("last-event-id")
    try:
        after = int(header_id or last_event_id or 0)
    except (TypeError, ValueError):
        after = 0

    async def generator():
        nonlocal after
        last_heartbeat = time.monotonic()
        while True:
            if await request.is_disconnected():
                break
            events = await run_in_threadpool(fetch_events, project_id, after, 500)
            for event in events:
                after = event["id"]
                payload = json.dumps(event, ensure_ascii=False)
                yield (
                    f"id: {event['id']}\n"
                    f"event: {event['type']}\n"
                    f"data: {payload}\n\n"
                )
            now = time.monotonic()
            if now - last_heartbeat >= 15:
                last_heartbeat = now
                yield ": heartbeat\n\n"
            await asyncio.sleep(0.5 if events else 1.0)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive",
                 "X-Accel-Buffering": "no"},
    )
