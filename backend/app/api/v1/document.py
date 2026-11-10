from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.projects import get_project
from app.core.db import get_db
from app.domain.models import Document
from app.domain.schemas import DocumentOut

router = APIRouter(prefix="/api/v1", tags=["document"])


@router.get("/projects/{project_id}/document", response_model=DocumentOut)
def get_document(project_id: str, db: Session = Depends(get_db)):
    get_project(db, project_id)
    document = db.scalars(
        select(Document)
        .where(Document.project_id == project_id)
        .order_by(Document.version.desc())
    ).first()
    if not document:
        raise HTTPException(404, "no document uploaded for this project")
    return document
