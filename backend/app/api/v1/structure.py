from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.v1.projects import get_project
from app.core.db import get_db
from app.domain.enums import LinkKind, SectionRole
from app.domain.models import Document, Link, Section
from app.domain.schemas import (
    LinkCreate,
    LinkOut,
    LinkPatch,
    ManualContextCreate,
    ManualContextPatch,
    SectionOut,
    SectionPatch,
)

router = APIRouter(prefix="/api/v1", tags=["structure"])


@router.get("/projects/{project_id}/sections", response_model=list[SectionOut])
def list_sections(project_id: str, db: Session = Depends(get_db)):
    get_project(db, project_id)
    return db.scalars(
        select(Section).where(Section.project_id == project_id).order_by(Section.position)
    ).all()


@router.patch("/sections/{section_id}", response_model=SectionOut)
def patch_section(section_id: str, patch: SectionPatch, db: Session = Depends(get_db)):
    section = db.get(Section, section_id)
    if not section:
        raise HTTPException(404, "section not found")
    if patch.role is not None:
        allowed = {role.value for role in SectionRole}
        if patch.role not in allowed:
            raise HTTPException(400, f"invalid role; expected one of {sorted(allowed)}")
        section.role = patch.role
    if patch.title is not None:
        section.title = patch.title
    if patch.extra_instructions is not None:
        section.extra_instructions = patch.extra_instructions.strip()
    db.commit()
    db.refresh(section)
    return section


@router.post("/projects/{project_id}/manual-context", response_model=SectionOut, status_code=201)
def create_manual_context(
    project_id: str, payload: ManualContextCreate, db: Session = Depends(get_db)
):
    project = get_project(db, project_id)
    title = payload.title.strip()
    text = payload.text.strip()
    if not title:
        raise HTTPException(400, "manual context title is required")
    if not text:
        raise HTTPException(400, "manual context text is required")

    document = db.scalars(
        select(Document)
        .where(Document.project_id == project_id)
        .order_by(Document.version.desc())
    ).first()
    root = db.scalars(
        select(Section)
        .where(Section.project_id == project_id, Section.parent_id.is_(None))
        .order_by(Section.position)
    ).first()
    max_position = db.scalar(
        select(func.max(Section.position)).where(Section.project_id == project_id)
    )
    base_lineage = list(root.lineage or [project.name]) if root else [project.name]
    lineage = [*base_lineage, title]
    section = Section(
        project_id=project_id,
        document_id=document.id if document else None,
        parent_id=root.id if root else None,
        number="",
        title=title,
        text=text,
        level=(root.level + 1) if root else 1,
        position=(max_position or 0) + 1,
        is_leaf=True,
        role=SectionRole.context.value,
        source="manual",
        lineage=lineage,
    )
    db.add(section)
    db.commit()
    db.refresh(section)
    return section


@router.patch("/sections/{section_id}/manual-context", response_model=SectionOut)
def update_manual_context(
    section_id: str, payload: ManualContextPatch, db: Session = Depends(get_db)
):
    section = db.get(Section, section_id)
    if not section or section.source != "manual":
        raise HTTPException(404, "manual context not found")
    if payload.title is None and payload.text is None:
        raise HTTPException(400, "provide a title or text to update")
    if payload.title is not None:
        title = payload.title.strip()
        if not title:
            raise HTTPException(400, "manual context title is required")
        section.title = title
        lineage = list(section.lineage or [])
        if lineage:
            lineage[-1] = title
        else:
            lineage = [title]
        section.lineage = lineage
    if payload.text is not None:
        text = payload.text.strip()
        if not text:
            raise HTTPException(400, "manual context text is required")
        section.text = text
    db.commit()
    db.refresh(section)
    return section


@router.delete("/sections/{section_id}/manual-context")
def delete_manual_context(section_id: str, db: Session = Depends(get_db)):
    section = db.get(Section, section_id)
    if not section or section.source != "manual":
        raise HTTPException(404, "manual context not found")
    db.query(Link).filter(
        or_(Link.source_id == section_id, Link.target_id == section_id)
    ).delete(synchronize_session=False)
    db.delete(section)
    db.commit()
    return {"deleted": True, "id": section_id}


@router.get("/projects/{project_id}/links", response_model=list[LinkOut])
def list_links(
    project_id: str,
    enabled: bool | None = Query(None),
    db: Session = Depends(get_db),
):
    get_project(db, project_id)
    query = select(Link).where(Link.project_id == project_id).order_by(Link.id)
    if enabled is not None:
        query = query.where(Link.enabled.is_(enabled))
    return db.scalars(query).all()


@router.post("/projects/{project_id}/links", response_model=LinkOut)
def create_link(project_id: str, payload: LinkCreate, db: Session = Depends(get_db)):
    get_project(db, project_id)
    if payload.source_id == payload.target_id:
        raise HTTPException(400, "a section cannot link to itself")
    for section_id in (payload.source_id, payload.target_id):
        section = db.get(Section, section_id)
        if not section or section.project_id != project_id:
            raise HTTPException(404, f"section {section_id} not found in this project")
    if payload.kind not in {kind.value for kind in LinkKind}:
        raise HTTPException(400, "invalid link kind")
    link = Link(
        project_id=project_id,
        source_id=payload.source_id,
        target_id=payload.target_id,
        kind=payload.kind,
        score=payload.score,
        reason=payload.reason,
        enabled=payload.enabled,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


@router.patch("/links/{link_id}", response_model=LinkOut)
def patch_link(link_id: int, patch: LinkPatch, db: Session = Depends(get_db)):
    link = db.get(Link, link_id)
    if not link:
        raise HTTPException(404, "link not found")
    if patch.enabled is not None:
        link.enabled = patch.enabled
    if patch.reason is not None:
        link.reason = patch.reason
    if patch.score is not None:
        link.score = patch.score
    db.commit()
    db.refresh(link)
    return link


@router.delete("/links/{link_id}")
def delete_link(link_id: int, db: Session = Depends(get_db)):
    link = db.get(Link, link_id)
    if not link:
        raise HTTPException(404, "link not found")
    db.delete(link)
    db.commit()
    return {"deleted": True, "id": link_id}
