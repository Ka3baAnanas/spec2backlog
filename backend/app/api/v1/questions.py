from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.projects import get_project
from app.core.db import get_db
from app.domain.enums import QuestionStatus
from app.domain.models import Question
from app.domain.schemas import QuestionOut, QuestionPatch

router = APIRouter(prefix="/api/v1", tags=["questions"])


@router.get("/projects/{project_id}/questions", response_model=list[QuestionOut])
def list_questions(project_id: str, db: Session = Depends(get_db)):
    get_project(db, project_id)
    return db.scalars(
        select(Question)
        .where(Question.project_id == project_id)
        .order_by(Question.created_at)
    ).all()


@router.patch("/questions/{question_id}", response_model=QuestionOut)
def update_question(question_id: str, patch: QuestionPatch, db: Session = Depends(get_db)):
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(404, "question not found")
    if patch.answer is not None:
        question.answer = patch.answer
        if question.status == QuestionStatus.open.value:
            question.status = QuestionStatus.answered.value
    if patch.status is not None:
        allowed = {status.value for status in QuestionStatus}
        if patch.status not in allowed:
            raise HTTPException(400, f"invalid status; expected one of {sorted(allowed)}")
        question.status = patch.status
    db.commit()
    db.refresh(question)
    return question
