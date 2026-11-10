"""INVEST-style quality checks and confidence scores."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import BacklogItem


def _story_checks(story: BacklogItem, test_count: int) -> dict:
    body = story.body or {}
    criteria = [item for item in body.get("acceptance_criteria", []) if str(item).strip()]
    checks = {
        "has_title": bool((story.title or "").strip()),
        "has_role": bool((body.get("as_a") or "").strip()),
        "has_want": bool((body.get("i_want") or "").strip()),
        "has_value": bool((body.get("so_that") or "").strip()),
        "has_acceptance_criteria": bool(criteria),
        "has_test": test_count >= 1,
        "is_small": len((story.title or "").split()) <= 20,
    }
    return checks


def score_project(db: Session, project_id: str) -> dict:
    items = list(
        db.scalars(select(BacklogItem).where(BacklogItem.project_id == project_id)).all()
    )
    tests_by_parent: dict[str, int] = {}
    for item in items:
        if item.kind == "test" and item.parent_item_id:
            tests_by_parent[item.parent_item_id] = tests_by_parent.get(item.parent_item_id, 0) + 1

    stories = [item for item in items if item.kind == "story"]
    for story in stories:
        checks = _story_checks(story, tests_by_parent.get(story.id, 0))
        score = sum(1 for value in checks.values() if value) / len(checks)
        story.confidence = round(score, 3)
        story.body = {**(story.body or {}), "quality": checks}

    db.commit()
    total = len(stories)
    average = round(sum(story.confidence for story in stories) / total, 3) if total else 0.0
    return {
        "stories": total,
        "average_confidence": average,
        "stories_with_criteria": sum(
            1 for story in stories if (story.body or {}).get("quality", {}).get("has_acceptance_criteria")
        ),
        "stories_with_test": sum(
            1 for story in stories if (story.body or {}).get("quality", {}).get("has_test")
        ),
    }
