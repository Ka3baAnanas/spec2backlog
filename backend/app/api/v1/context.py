from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.domain.models import Section
from app.domain.schemas import ContextOut
from app.modules.context.builder import context_preview, snapshot_context

router = APIRouter(prefix="/api/v1", tags=["context"])


@router.get("/sections/{section_id}/context", response_model=ContextOut)
def get_context(section_id: str, db: Session = Depends(get_db)):
    section = db.get(Section, section_id)
    if not section:
        raise HTTPException(404, "section not found")
    snapshot_context(db, section)
    return context_preview(db, section)
