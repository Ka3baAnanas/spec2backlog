"""INVEST-style quality checks and confidence scores."""

import re
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import BacklogItem


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", (text or "").lower())).strip()


def _then_part(criterion: str) -> str:
    lower = (criterion or "").lower()
    marker = lower.rfind("then ")
    if marker >= 0:
        return criterion[marker + 5 :].strip(" ,.")
    return (criterion or "").strip(" ,.")


def _test_covers_criterion(test: BacklogItem, criteria: list[str]) -> bool:
    body = test.body or {}
    test_text = _normalize(f"{test.title} {body.get('expected', '')}")
    if not test_text:
        return False
    for criterion in criteria:
        target = _normalize(_then_part(criterion))
        if len(target) < 4:
            continue
        if target in test_text or test_text in target:
            return True
        if SequenceMatcher(None, target, test_text).ratio() >= 0.55:
            return True
    return False


def _story_checks(story: BacklogItem, tests: list[BacklogItem]) -> dict:
    body = story.body or {}
    criteria = [item for item in body.get("acceptance_criteria", []) if str(item).strip()]
    evidence = [item for item in body.get("source_evidence", []) if str(item).strip()]
    checks = {
        "has_acceptance_criteria": len(criteria) >= 3,
        "has_tests": len(tests) >= 1,
        "has_source_evidence": len(evidence) >= 2,
        "no_ambiguity_flag": not bool(body.get("ambiguity_flag")),
        "tests_cover_criteria": bool(tests)
        and all(_test_covers_criterion(test, criteria) for test in tests),
    }
    return checks


def score_project(db: Session, project_id: str) -> dict:
    items = list(
        db.scalars(select(BacklogItem).where(BacklogItem.project_id == project_id)).all()
    )
    tests_by_parent: dict[str, list[BacklogItem]] = {}
    for item in items:
        if item.kind == "test" and item.parent_item_id:
            tests_by_parent.setdefault(item.parent_item_id, []).append(item)

    stories = [item for item in items if item.kind == "story"]
    for story in stories:
        checks = _story_checks(story, tests_by_parent.get(story.id, []))
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
            1 for story in stories if (story.body or {}).get("quality", {}).get("has_tests")
        ),
    }
