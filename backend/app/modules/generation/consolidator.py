"""Dedupe/merge generated stories across leaves and assign stable keys."""

import re
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import BacklogItem, Project, Question, Section
from app.modules.generation.generator import GenerationResult

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", _PUNCT_RE.sub(" ", (title or "").lower())).strip()


def _similar(left: str, right: str) -> bool:
    if not left or not right:
        return False
    if left == right:
        return True
    return SequenceMatcher(None, left, right).ratio() >= 0.88


def _unique(values: list) -> list:
    seen = set()
    out = []
    for value in values:
        marker = str(value)
        if marker not in seen:
            seen.add(marker)
            out.append(value)
    return out


def _next_number(items: list[BacklogItem], kind: str) -> int:
    highest = 0
    for item in items:
        if item.kind != kind or not item.key:
            continue
        digits = re.findall(r"(\d+)$", item.key)
        if digits:
            highest = max(highest, int(digits[0]))
    return highest + 1


def consolidate(
    db: Session, project: Project, results: list[GenerationResult]
) -> dict:
    sections = {
        section.id: section
        for section in db.scalars(select(Section).where(Section.project_id == project.id))
    }
    existing_items = list(
        db.scalars(select(BacklogItem).where(BacklogItem.project_id == project.id)).all()
    )

    epics: list[BacklogItem] = []
    stories: list[BacklogItem] = []
    tests: list[BacklogItem] = []
    story_index: dict[str, BacklogItem] = {}
    per_result_stories: dict[str, dict[str, BacklogItem]] = {}

    for result in results:
        output = result.output or {}
        section = sections.get(result.section_id)
        epic_title = ((output.get("epic") or {}).get("title") or (section.title if section else ""))
        epic = BacklogItem(
            project_id=project.id,
            kind="epic",
            source_section_id=result.section_id,
            source_sections=[result.section_id],
            title=epic_title,
            body={
                "section_id": result.section_id,
                "section_number": section.number if section else "",
                "section_title": section.title if section else "",
            },
            status="proposed",
        )
        db.add(epic)
        db.flush()
        epics.append(epic)

        section_story_map: dict[str, BacklogItem] = {}
        for story_data in output.get("stories") or []:
            title = story_data.get("title", "")
            normalized = normalize_title(title)
            match = None
            for key, candidate in story_index.items():
                if _similar(normalized, key):
                    match = candidate
                    break

            if match is not None:
                match.source_sections = _unique(
                    (match.source_sections or []) + [result.section_id]
                )
                body = dict(match.body or {})
                body["acceptance_criteria"] = _unique(
                    (body.get("acceptance_criteria") or [])
                    + (story_data.get("acceptance_criteria") or [])
                )
                body["merged_from"] = _unique(
                    (body.get("merged_from") or []) + [result.section_id]
                )
                match.body = body
                section_story_map[title] = match
                continue

            story = BacklogItem(
                project_id=project.id,
                kind="story",
                parent_item_id=epic.id,
                source_section_id=result.section_id,
                source_sections=[result.section_id],
                title=title,
                body={**story_data, "section_id": result.section_id,
                      "merged_from": [result.section_id]},
                status="proposed",
            )
            db.add(story)
            db.flush()
            stories.append(story)
            story_index[normalized] = story
            section_story_map[title] = story

        per_result_stories[result.section_id] = section_story_map

        for question in output.get("questions") or []:
            text = question if isinstance(question, str) else str(question)
            if text.strip():
                db.add(
                    Question(
                        project_id=project.id,
                        section_id=result.section_id,
                        text=text.strip(),
                        status="open",
                    )
                )

    for result in results:
        output = result.output or {}
        story_map = per_result_stories.get(result.section_id, {})
        first_story = next(iter(story_map.values()), None)
        for test_data in output.get("tests") or []:
            parent = story_map.get(test_data.get("story_title", ""), first_story)
            test = BacklogItem(
                project_id=project.id,
                kind="test",
                parent_item_id=parent.id if parent else None,
                source_section_id=result.section_id,
                source_sections=[result.section_id],
                title=test_data.get("title", ""),
                body={**test_data, "section_id": result.section_id},
                status="proposed",
            )
            db.add(test)
            tests.append(test)

    db.flush()

    epic_number = _next_number(existing_items, "epic")
    for epic in epics:
        epic.key = f"EP-{epic_number:02d}"
        epic_number += 1
    story_number = _next_number(existing_items, "story")
    for story in stories:
        story.key = f"US-{story_number:03d}"
        story_number += 1
    test_number = _next_number(existing_items, "test")
    for test in tests:
        test.key = f"TC-{test_number:03d}"
        test_number += 1

    db.commit()
    return {
        "epics": len(epics),
        "stories": len(stories),
        "tests": len(tests),
        "merged_stories": sum(
            1 for story in stories if len(story.source_sections or []) > 1
        ),
    }
