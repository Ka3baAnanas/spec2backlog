"""Human review: approve/edit/reject with audit trail, and single-item regeneration."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import ItemStatus
from app.domain.models import BacklogItem, Project, ReviewEvent, Section
from app.modules.generation.generator import generate_for_section


def _event(db: Session, item: BacklogItem, action: str, before: dict, by: str) -> None:
    db.add(
        ReviewEvent(
            project_id=item.project_id,
            item_id=item.id,
            action=action,
            before=before,
            after={"title": item.title, "body": item.body, "status": item.status},
            by=by,
        )
    )


def patch_item(
    db: Session,
    item: BacklogItem,
    *,
    title: str | None = None,
    body: dict | None = None,
    status: str | None = None,
    by: str = "ba",
) -> BacklogItem:
    before = {"title": item.title, "body": item.body, "status": item.status}
    if title is not None:
        item.title = title
    if body is not None:
        item.body = body
    if status is not None:
        item.status = ItemStatus(status).value
    elif title is not None or body is not None:
        item.status = ItemStatus.edited.value

    if item.project_id:
        project = db.get(Project, item.project_id)
        if project and project.status == "generated":
            project.status = "in_review"
    _event(db, item, item.status, before, by)
    db.commit()
    db.refresh(item)
    return item


def approve_backlog(db: Session, project: Project, by: str = "ba") -> dict:
    items = list(
        db.scalars(select(BacklogItem).where(BacklogItem.project_id == project.id)).all()
    )
    approved = 0
    for item in items:
        if item.status != ItemStatus.rejected.value:
            item.status = ItemStatus.approved.value
            approved += 1
            _event(db, item, "approve", {"status": "proposed"}, by)
    project.status = "approved"
    project.error = None
    db.commit()
    return {"approved": approved, "status": project.status}


def _pick_output(item: BacklogItem, output: dict) -> tuple[str, dict]:
    stories = output.get("stories") or []
    if item.kind == "epic":
        epic = output.get("epic") or {}
        return epic.get("title") or item.title, {**(item.body or {}), "regenerated": True}
    if item.kind == "test":
        tests = [test for story in stories for test in (story.get("tests") or [])]
        if tests:
            return tests[0].get("title") or item.title, {**tests[0], "regenerated": True}
    if stories:
        story = {key: value for key, value in stories[0].items() if key != "tests"}
        return story.get("title") or item.title, {**story, "regenerated": True}
    return item.title, item.body or {}


def regenerate_item(
    db: Session, item: BacklogItem, instruction: str = "", by: str = "ba"
) -> BacklogItem:
    section = db.get(Section, item.source_section_id)
    project = db.get(Project, item.project_id)
    if not section or not project:
        raise LookupError("source section or project not found")
    result = generate_for_section(db, project, section, instruction=instruction)
    if result.status == "failed" or not result.output:
        raise RuntimeError(result.error or "generation failed")

    before = {"title": item.title, "body": item.body, "status": item.status}
    title, body = _pick_output(item, result.output)
    item.title = title
    item.body = {**body, "regeneration_instruction": instruction}
    item.status = ItemStatus.edited.value
    if section.id not in (item.source_sections or []):
        item.source_sections = list(item.source_sections or []) + [section.id]
    if project.status in ("generated", "in_review", "approved"):
        project.status = "in_review"
    _event(db, item, "regenerate", before, by)
    db.commit()
    db.refresh(item)
    return item
