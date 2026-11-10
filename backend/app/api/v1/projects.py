from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.events import emit
from app.domain.models import (
    BacklogItem,
    ContextPack,
    Document,
    GenerationTrace,
    GlossaryTerm,
    Link,
    Project,
    Question,
    ReviewEvent,
    Section,
)
from app.domain.schemas import ProjectOut
from app.modules.ingestion.service import prepare_project
from app.modules.knowledge.service import clear_knowledge

router = APIRouter(prefix="/api/v1", tags=["projects"])


def get_project(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    return project


def not_implemented(message: str) -> None:
    raise HTTPException(501, message)


@router.get("/health")
def health():
    return {"ok": True}


@router.post("/projects", response_model=ProjectOut)
async def create_project(
    name: str = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    filename = file.filename or "specification"
    suffix = Path(filename).suffix.lower()
    if suffix not in (".docx", ".pdf"):
        raise HTTPException(415, "Unsupported file type; expected .docx or .pdf")

    project = Project(name=name.strip() or Path(filename).stem, status="uploaded")
    db.add(project)
    db.commit()
    db.refresh(project)

    upload_dir = Path(settings.uploads_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    destination = upload_dir / f"{project.id}{suffix}"
    content = await file.read()
    destination.write_bytes(content)

    try:
        await run_in_threadpool(prepare_project, db, project, destination, filename)
    except ValueError as exc:
        db.delete(project)
        db.commit()
        destination.unlink(missing_ok=True)
        raise HTTPException(415, str(exc)) from exc
    except Exception as exc:
        db.rollback()
        project = db.get(Project, project.id)
        if project:
            project.status = "failed"
            project.error = f"{type(exc).__name__}: {exc}"
            db.commit()
        emit(project.id, "ingestion", "error",
             f"Preparation failed: {type(exc).__name__}: {exc}", {"error": str(exc)})
        raise HTTPException(500, f"Preparation failed: {exc}") from exc

    db.refresh(project)
    return project


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    return db.scalars(select(Project).order_by(Project.created_at.desc())).all()


@router.get("/projects/{project_id}", response_model=ProjectOut)
def read_project(project_id: str, db: Session = Depends(get_db)):
    return get_project(db, project_id)


@router.delete("/projects/{project_id}")
def delete_project(project_id: str, db: Session = Depends(get_db)):
    project = get_project(db, project_id)
    documents = db.scalars(
        select(Document).where(Document.project_id == project_id)
    ).all()
    for model in (
        Link,
        GlossaryTerm,
        ContextPack,
        BacklogItem,
        Question,
        GenerationTrace,
        ReviewEvent,
        Section,
        Document,
    ):
        db.query(model).filter(model.project_id == project_id).delete(synchronize_session=False)
    db.delete(project)
    db.commit()
    clear_knowledge(project_id)
    for document in documents:
        if document.path:
            Path(document.path).unlink(missing_ok=True)
    return {"deleted": True, "id": project_id}
