"""Evaluation metrics for a project run."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import BacklogItem, Project, ReviewEvent
from app.modules.export.traceability import matrix


def project_metrics(db: Session, project: Project) -> dict:
    coverage = matrix(db, project)
    items = list(
        db.scalars(select(BacklogItem).where(BacklogItem.project_id == project.id)).all()
    )
    stories = [item for item in items if item.kind == "story"]
    reviews = list(
        db.scalars(select(ReviewEvent).where(ReviewEvent.project_id == project.id)).all()
    )
    edited = sum(1 for event in reviews if event.action == "edited")
    approved = sum(1 for story in stories if story.status == "approved")
    return {
        "coverage": coverage["coverage"],
        "acceptance_rate": round((approved / len(stories)) * 100, 1) if stories else 0.0,
        "edit_rate": round((edited / len(stories)) * 100, 1) if stories else 0.0,
        "items": len(items),
        "stories": len(stories),
        "review_events": len(reviews),
    }
