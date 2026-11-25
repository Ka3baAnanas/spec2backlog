from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.projects import get_project
from app.core.db import get_db
from app.core.events import emit
from app.core.jobs import get_run, start_generation
from app.domain.models import BacklogItem, Document, GenerationTrace, Link, Question, Section
from app.modules.ingestion.service import prepare_project

router = APIRouter(prefix="/api/v1", tags=["pipeline"])


@router.post("/projects/{project_id}/pipeline/prepare")
def prepare(project_id: str, db: Session = Depends(get_db)):
    project = get_project(db, project_id)
    document = db.scalars(
        select(Document)
        .where(Document.project_id == project_id)
        .order_by(Document.version.desc())
    ).first()
    if not document or not document.path:
        raise HTTPException(409, "no uploaded document to prepare")
    path = Path(document.path)
    if not path.exists():
        raise HTTPException(409, "uploaded document is no longer available")
    try:
        result = prepare_project(db, project, path, document.filename)
    except ValueError as exc:
        raise HTTPException(415, str(exc)) from exc
    return result


@router.post("/projects/{project_id}/pipeline/approve-context")
def approve_context(project_id: str, db: Session = Depends(get_db)):
    project = get_project(db, project_id)
    if project.context_approved:
        return {"project_id": project_id, "context_approved": True,
                "status": project.status}
    if project.status != "awaiting_context_approval":
        raise HTTPException(
            409,
            f"context cannot be approved from status '{project.status}' "
            "(prepare the project first)",
        )
    project.context_approved = True
    db.commit()
    emit(project_id, "context", "info", "Context approved by human",
         {"checkpoint": "context_approval"})
    return {"project_id": project_id, "context_approved": True, "status": project.status}


@router.post("/projects/{project_id}/pipeline/generate")
def generate(project_id: str, db: Session = Depends(get_db)):
    project = get_project(db, project_id)
    if not project.context_approved:
        raise HTTPException(409, "context must be approved before generation")
    if project.status == "generating":
        raise HTTPException(409, "generation is already running")
    has_requirements = db.scalar(
        select(func.count(Section.id)).where(
            Section.project_id == project_id, Section.role == "requirement"
        )
    )
    if not has_requirements:
        raise HTTPException(409, "no requirement section to generate")
    project.status = "generating"
    project.error = None
    db.commit()
    return start_generation(project_id, only_failed=False)


@router.post("/projects/{project_id}/pipeline/retry-failed")
def retry_failed(project_id: str, db: Session = Depends(get_db)):
    project = get_project(db, project_id)
    if not project.context_approved:
        raise HTTPException(409, "context must be approved before generation")
    if project.status == "generating":
        raise HTTPException(409, "generation is already running")
    failed_sections = db.scalar(
        select(func.count(GenerationTrace.id)).where(
            GenerationTrace.project_id == project_id, GenerationTrace.status == "failed"
        )
    )
    completed_sections = db.scalar(
        select(func.count(GenerationTrace.id)).where(
            GenerationTrace.project_id == project_id,
            GenerationTrace.status.in_(["ok", "retried"]),
        )
    )
    if not failed_sections and not completed_sections:
        raise HTTPException(409, "no generation result to retry")
    project.status = "generating"
    project.error = None
    db.commit()
    return start_generation(project_id, resume=True)


@router.post("/projects/{project_id}/pipeline/recover")
def recover(project_id: str, db: Session = Depends(get_db)):
    project = get_project(db, project_id)
    if project.status != "generating":
        raise HTTPException(409, "project is not generating")
    run = get_run(project_id)
    if run and run.get("status") == "running":
        raise HTTPException(409, "generation is already running")
    emit(
        project_id,
        "generation",
        "warning",
        "Generation was interrupted; resuming pending sections",
        {"resume": True},
    )
    return start_generation(project_id, resume=True)


@router.get("/projects/{project_id}/pipeline/status")
def pipeline_status(project_id: str, db: Session = Depends(get_db)):
    project = get_project(db, project_id)
    counts = {
        "sections": db.scalar(
            select(func.count(Section.id)).where(Section.project_id == project_id)
        ),
        "requirement_sections": db.scalar(
            select(func.count(Section.id)).where(
                Section.project_id == project_id, Section.role == "requirement"
            )
        ),
        "links": db.scalar(
            select(func.count(Link.id)).where(Link.project_id == project_id)
        ),
        "items": db.scalar(
            select(func.count(BacklogItem.id)).where(BacklogItem.project_id == project_id)
        ),
        "questions": db.scalar(
            select(func.count(Question.id)).where(Question.project_id == project_id)
        ),
        "traces": db.scalar(
            select(func.count(GenerationTrace.id)).where(
                GenerationTrace.project_id == project_id
            )
        ),
    }
    return {
        "project_id": project_id,
        "status": project.status,
        "context_approved": project.context_approved,
        "error": project.error,
        "progress": counts,
        "run": get_run(project_id),
    }
