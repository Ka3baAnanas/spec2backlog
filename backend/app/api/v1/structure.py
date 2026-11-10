from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.projects import get_project
from app.core.db import get_db
from app.domain.enums import LinkKind, SectionRole
from app.domain.models import Link, Section
from app.domain.schemas import LinkCreate, LinkOut, LinkPatch, SectionOut, SectionPatch

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
    db.commit()
    db.refresh(section)
    return section


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
