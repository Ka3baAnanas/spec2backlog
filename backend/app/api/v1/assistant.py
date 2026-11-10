from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.projects import get_project
from app.core.db import get_db
from app.domain.schemas import AskRequest, AskResponse
from app.modules.assistant.ask import answer_question

router = APIRouter(prefix="/api/v1", tags=["assistant"])


@router.post("/projects/{project_id}/ask", response_model=AskResponse)
def ask(project_id: str, payload: AskRequest, db: Session = Depends(get_db)):
    project = get_project(db, project_id)
    return answer_question(db, project, payload.question)
