from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.projects import get_project, not_implemented
from app.core.db import get_db

router = APIRouter(prefix="/api/v1", tags=["versions"])


@router.post("/projects/{project_id}/versions")
def create_version(project_id: str, db: Session = Depends(get_db)):
    get_project(db, project_id)
    not_implemented(
        "Spec v2 upload and impact analysis are not implemented yet (HTTP 501). "
        "Planned: upload v2 -> diff sections -> list impacted backlog items."
    )
