"""Export payload: approved backlog hierarchy, questions, traceability and audit trail."""

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import BacklogItem, Document, Project, Question, ReviewEvent, Section

APPROVED = ("approved", "edited")
QUESTION_ORDER = {"Blocking": 0, "Important": 1, "Minor": 2}


def _items(db: Session, project_id: str) -> list[BacklogItem]:
    return list(
        db.scalars(
            select(BacklogItem)
            .where(BacklogItem.project_id == project_id)
            .order_by(BacklogItem.kind, BacklogItem.key, BacklogItem.id)
        ).all()
    )


def _sections(db: Session, project_id: str) -> dict[str, Section]:
    return {
        section.id: section
        for section in db.scalars(
            select(Section).where(Section.project_id == project_id).order_by(Section.position)
        )
    }


def _story_dict(story: BacklogItem, source_sections: list[dict], tests: list[BacklogItem]) -> dict:
    return {
        "item": story,
        "title": story.title,
        "body": story.body or {},
        "status": story.status,
        "confidence": story.confidence,
        "source_sections": source_sections,
        "tests": tests,
    }


def _section_dict(section: Section | None) -> dict:
    if not section:
        return {"number": "", "title": "Unknown section"}
    return {"number": section.number, "title": section.title}


def build_export_payload(db: Session, project: Project) -> dict:
    sections = _sections(db, project.id)
    items = _items(db, project.id)
    by_id = {item.id: item for item in items}
    by_parent: dict[str, list[BacklogItem]] = defaultdict(list)
    for item in items:
        if item.parent_item_id:
            by_parent[item.parent_item_id].append(item)

    stories = [item for item in items if item.kind == "story" and item.status in APPROVED]
    story_ids = {story.id for story in stories}
    tests_by_story: dict[str, list[BacklogItem]] = defaultdict(list)
    for item in items:
        if item.kind == "test" and item.parent_item_id in story_ids:
            tests_by_story[item.parent_item_id].append(item)

    story_payload: dict[str, dict] = {}
    for story in stories:
        source_ids = []
        for section_id in [story.source_section_id, *(story.source_sections or [])]:
            if section_id and section_id not in source_ids:
                source_ids.append(section_id)
        story_payload[story.id] = _story_dict(
            story,
            [_section_dict(sections.get(section_id)) for section_id in source_ids],
            tests_by_story.get(story.id, []),
        )

    epics = []
    feature_count = 0
    for epic in [item for item in items if item.kind == "epic"]:
        features = []
        direct_stories = []
        for feature in by_parent.get(epic.id, []):
            if feature.kind != "feature":
                if feature.kind == "story" and feature.id in story_payload:
                    direct_stories.append(story_payload[feature.id])
                continue
            feature_stories = [
                story_payload[story.id]
                for story in by_parent.get(feature.id, [])
                if story.kind == "story" and story.id in story_payload
            ]
            if not feature_stories:
                continue
            feature_count += 1
            features.append(
                {
                    "item": feature,
                    "title": feature.title,
                    "summary": (feature.body or {}).get("summary", ""),
                    "stories": feature_stories,
                }
            )
        if direct_stories:
            features.append(
                {
                    "item": None,
                    "title": "General",
                    "summary": "",
                    "stories": direct_stories,
                }
            )
        if features:
            epics.append(
                {
                    "item": epic,
                    "title": epic.title,
                    "summary": (epic.body or {}).get("summary", ""),
                    "features": features,
                }
            )

    questions = list(
        db.scalars(
            select(Question)
            .where(Question.project_id == project.id, Question.status == "open")
            .order_by(Question.created_at)
        ).all()
    )
    questions.sort(key=lambda item: (QUESTION_ORDER.get(item.priority, 1), item.created_at))
    question_payload = [
        {
            "item": question,
            "priority": question.priority,
            "text": question.text,
            "status": question.status,
            "answer": question.answer,
            "source": _section_dict(sections.get(question.section_id)),
        }
        for question in questions
    ]

    latest_event: dict[str, ReviewEvent] = {}
    for event in db.scalars(
        select(ReviewEvent)
        .where(ReviewEvent.project_id == project.id)
        .order_by(ReviewEvent.at, ReviewEvent.id)
    ).all():
        if event.item_id:
            latest_event[event.item_id] = event

    validation = []
    for item in items:
        if item.status not in ("approved", "edited", "rejected"):
            continue
        event = latest_event.get(item.id)
        validation.append(
            {
                "item": item,
                "parent": by_id.get(item.parent_item_id) if item.parent_item_id else None,
                "action": event.action if event else "status set",
                "before_status": (event.before or {}).get("status", "") if event else "",
                "after_status": (event.after or {}).get("status", item.status) if event else item.status,
                "by": event.by if event else "",
                "at": event.at if event else None,
            }
        )

    requirements = [section for section in sections.values() if section.role == "requirement"]
    covered = 0
    for section in requirements:
        if any(
            section.id in [story["item"].source_section_id, *(story["item"].source_sections or [])]
            for story in story_payload.values()
        ):
            covered += 1

    latest_document = db.scalars(
        select(Document)
        .where(Document.project_id == project.id)
        .order_by(Document.version.desc())
    ).first()

    return {
        "project": project,
        "version": latest_document.version if latest_document else 1,
        "sections": sections,
        "epics": epics,
        "stories": list(story_payload.values()),
        "questions": question_payload,
        "validation": validation,
        "feature_count": feature_count,
        "coverage": round((covered / len(requirements)) * 100, 1) if requirements else 0.0,
        "requirement_sections": len(requirements),
    }
