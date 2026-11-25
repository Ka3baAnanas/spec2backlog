from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.projects import get_project
from app.core.db import get_db
from app.domain.models import BacklogItem, GenerationTrace
from app.domain.schemas import BacklogItemOut, ItemPatch, ItemRegenerate
from app.modules.review.service import approve_backlog, patch_item, regenerate_item

router = APIRouter(prefix="/api/v1", tags=["backlog"])


def _item_dict(item: BacklogItem) -> dict:
    return BacklogItemOut.model_validate(item).model_dump()


def _get_item(db: Session, item_id: str) -> BacklogItem:
    item = db.get(BacklogItem, item_id)
    if not item:
        raise HTTPException(404, "backlog item not found")
    return item


@router.get("/projects/{project_id}/backlog")
def get_backlog(project_id: str, db: Session = Depends(get_db)):
    get_project(db, project_id)
    items = list(
        db.scalars(
            select(BacklogItem)
            .where(BacklogItem.project_id == project_id)
            .order_by(BacklogItem.kind, BacklogItem.key, BacklogItem.id)
        ).all()
    )
    by_parent: dict[str, list[BacklogItem]] = {}
    for item in items:
        if item.parent_item_id:
            by_parent.setdefault(item.parent_item_id, []).append(item)

    epics = []
    for epic in [item for item in items if item.kind == "epic"]:
        features = []
        flat_stories = []
        for feature in by_parent.get(epic.id, []):
            if feature.kind != "feature":
                continue
            stories = []
            for story in by_parent.get(feature.id, []):
                if story.kind != "story":
                    continue
                story_dict = _item_dict(story)
                story_dict["tests"] = [
                    _item_dict(test) for test in by_parent.get(story.id, [])
                    if test.kind == "test"
                ]
                stories.append(story_dict)
                flat_stories.append(story_dict)
            feature_dict = _item_dict(feature)
            feature_dict["stories"] = stories
            features.append(feature_dict)
        epic_dict = _item_dict(epic)
        epic_dict["features"] = features
        epic_dict["stories"] = flat_stories
        epics.append(epic_dict)

    counts = {
        "epics": sum(1 for item in items if item.kind == "epic"),
        "features": sum(1 for item in items if item.kind == "feature"),
        "stories": sum(1 for item in items if item.kind == "story"),
        "tests": sum(1 for item in items if item.kind == "test"),
    }
    by_status: dict[str, int] = {}
    for item in items:
        by_status[item.status] = by_status.get(item.status, 0) + 1

    return {
        "project_id": project_id,
        "epics": epics,
        "stats": {**counts, "by_status": by_status, "total": len(items)},
    }


@router.patch("/items/{item_id}", response_model=BacklogItemOut)
def update_item(item_id: str, patch: ItemPatch, db: Session = Depends(get_db)):
    item = _get_item(db, item_id)
    try:
        return patch_item(
            db, item, title=patch.title, body=patch.body, status=patch.status, by=patch.by
        )
    except ValueError as exc:
        raise HTTPException(400, f"invalid status: {exc}") from exc


@router.post("/items/{item_id}/regenerate", response_model=BacklogItemOut)
def regenerate(item_id: str, payload: ItemRegenerate, db: Session = Depends(get_db)):
    item = _get_item(db, item_id)
    try:
        return regenerate_item(db, item, payload.instruction, payload.by)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(502, f"regeneration failed: {exc}") from exc


@router.get("/items/{item_id}/trace")
def item_trace(item_id: str, db: Session = Depends(get_db)):
    item = _get_item(db, item_id)
    trace = db.scalars(
        select(GenerationTrace)
        .where(
            GenerationTrace.project_id == item.project_id,
            GenerationTrace.section_id == item.source_section_id,
        )
        .order_by(GenerationTrace.id.desc())
    ).first()
    if not trace:
        raise HTTPException(404, "no generation trace for this item's source section")
    return {
        "item_id": item.id,
        "section_id": trace.section_id,
        "prompt": trace.prompt,
        "response_json": trace.response_json,
        "links": trace.links or [],
        "global_context_ids": trace.global_context_ids or [],
        "duration_ms": trace.duration_ms,
        "attempts": trace.attempts,
        "status": trace.status,
        "error": trace.error,
        "items_created": trace.items_created or {},
    }


@router.post("/projects/{project_id}/backlog/approve")
def approve(project_id: str, db: Session = Depends(get_db)):
    project = get_project(db, project_id)
    total = db.scalar(
        select(BacklogItem.id).where(BacklogItem.project_id == project_id).limit(1)
    )
    if not total:
        raise HTTPException(409, "there is no backlog to approve")
    return approve_backlog(db, project)
