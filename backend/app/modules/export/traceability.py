"""Traceability matrix: section -> stories -> tests, with coverage."""

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import BacklogItem, Project, Section


def project_items(db: Session, project_id: str) -> list[BacklogItem]:
    return list(
        db.scalars(
            select(BacklogItem)
            .where(BacklogItem.project_id == project_id)
            .order_by(BacklogItem.kind, BacklogItem.key)
        ).all()
    )


def matrix(db: Session, project: Project) -> dict:
    sections = list(
        db.scalars(
            select(Section)
            .where(Section.project_id == project.id)
            .order_by(Section.position)
        ).all()
    )
    items = project_items(db, project.id)
    stories_by_section: dict[str, list[BacklogItem]] = defaultdict(list)
    tests_by_story: dict[str, list[BacklogItem]] = defaultdict(list)

    for item in items:
        if item.kind == "story":
            for section_id in [item.source_section_id, *(item.source_sections or [])]:
                if item not in stories_by_section[section_id]:
                    stories_by_section[section_id].append(item)
        elif item.kind == "test" and item.parent_item_id:
            tests_by_story[item.parent_item_id].append(item)

    rows = []
    requirement_sections = [section for section in sections if section.role == "requirement"]
    covered = 0
    for section in requirement_sections:
        stories = stories_by_section.get(section.id, [])
        if stories:
            covered += 1
        rows.append(
            {
                "section_id": section.id,
                "number": section.number,
                "title": section.title,
                "role": section.role,
                "stories": [
                    {
                        "id": story.id,
                        "key": story.key,
                        "title": story.title,
                        "status": story.status,
                        "tests": [
                            {"id": test.id, "key": test.key, "title": test.title,
                             "status": test.status}
                            for test in tests_by_story.get(story.id, [])
                        ],
                    }
                    for story in stories
                ],
                "covered": bool(stories),
            }
        )

    total = len(requirement_sections)
    return {
        "project_id": project.id,
        "rows": rows,
        "coverage": round((covered / total) * 100, 1) if total else 0.0,
        "stats": {
            "requirement_sections": total,
            "covered_sections": covered,
            "stories": sum(1 for item in items if item.kind == "story"),
            "tests": sum(1 for item in items if item.kind == "test"),
        },
    }


def backlog_rows(db: Session, project: Project) -> list[dict]:
    sections = {
        section.id: section
        for section in db.scalars(select(Section).where(Section.project_id == project.id))
    }
    items = project_items(db, project.id)
    by_id = {item.id: item for item in items}
    rows = []
    for item in items:
        source = sections.get(item.source_section_id)
        parent = by_id.get(item.parent_item_id) if item.parent_item_id else None
        rows.append(
            {
                "key": item.key,
                "kind": item.kind,
                "title": item.title,
                "parent": parent.key if parent else "",
                "source": " > ".join(source.lineage) if source else "",
                "status": item.status,
                "confidence": item.confidence,
                "details": str(item.body or {}),
            }
        )
    return rows
