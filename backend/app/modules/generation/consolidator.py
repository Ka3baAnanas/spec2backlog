"""Two-pass consolidation: group detailed stories into epics and features."""

import json
import re
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import BacklogItem, Project, Question, Section
from app.modules.generation.generator import GenerationResult
from app.modules.generation.prompts import load_template
from app.modules.generation.schema import (
    consolidation_json_schema,
    validate_consolidation,
)

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_NUMBER_PREFIX_RE = re.compile(r"^\d+(?:\.\d+)*\s*")
_QUESTION_PRIORITY = {"Blocking": 3, "Important": 2, "Minor": 1}


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


def _epic_hint(section: Section | None) -> str:
    if not section:
        return "Project backlog"
    lineage = section.lineage or []
    if len(lineage) > 1:
        return lineage[1]
    return section.title or "Project backlog"


def _epic_title(hint: str) -> str:
    return _NUMBER_PREFIX_RE.sub("", hint or "").strip() or "Project scope"


def _clean_question_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _build_entries(results: list[GenerationResult], sections: dict[str, Section]) -> list[dict]:
    entries: list[dict] = []
    for result in results:
        output = result.output or {}
        section = sections.get(result.section_id)
        for story in output.get("stories") or []:
            title = (story.get("title") or "").strip()
            if not title:
                continue
            marker = normalize_title(title)
            match = next(
                (entry for entry in entries if _similar(marker, entry["marker"])),
                None,
            )
            if match is not None:
                match["source_sections"] = _unique(
                    (match["source_sections"] or []) + [result.section_id]
                )
                match["tests"] = _unique(
                    (match["tests"] or []) + (story.get("tests") or [])
                )
                body = dict(match["story"])
                body["acceptance_criteria"] = _unique(
                    (body.get("acceptance_criteria") or [])
                    + (story.get("acceptance_criteria") or [])
                )
                match["story"] = body
                continue
            entries.append(
                {
                    "ref": "",
                    "marker": marker,
                    "story": story,
                    "section": section,
                    "section_id": result.section_id,
                    "source_sections": [result.section_id],
                    "tests": story.get("tests") or [],
                }
            )
    for index, entry in enumerate(entries, 1):
        entry["ref"] = f"S{index}"
    return entries


def _consolidation_payload(entries: list[dict]) -> list[dict]:
    payload = []
    for entry in entries:
        story = entry["story"]
        section = entry["section"]
        payload.append(
            {
                "ref": entry["ref"],
                "title": story.get("title", ""),
                "persona": story.get("persona") or story.get("as_a", ""),
                "goal": story.get("goal") or story.get("i_want", ""),
                "benefit": story.get("benefit") or story.get("so_that", ""),
                "description": (story.get("description") or "")[:220],
                "priority": story.get("priority", "should"),
                "feature_hint": story.get("feature_hint", ""),
                "section": (
                    f"{section.number} {section.title}".strip() if section else ""
                ),
                "epic_hint": _epic_hint(section),
                "source_evidence": (story.get("source_evidence") or [])[:2],
            }
        )
    return payload


def _fallback_plan(entries: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for entry in entries:
        groups.setdefault(_epic_hint(entry["section"]), []).append(entry)

    if len(groups) > 9:
        ordered = list(groups.items())
        kept = ordered[:8]
        extra = [entry for _, items in ordered[8:] for entry in items]
        kept.append(("Additional scope", extra))
        groups = dict(kept)

    if len(groups) < 5 and len(entries) >= 5:
        refs = [entry["ref"] for entry in entries]
        entries_by_ref = {entry["ref"]: entry for entry in entries}
        groups = {}
        for index in range(5):
            chunk = refs[index::5]
            if chunk:
                groups[f"Delivery theme {index + 1}"] = [entries_by_ref[ref] for ref in chunk]

    plan = []
    for hint, items in groups.items():
        features: dict[str, list[str]] = {}
        for entry in items:
            feature = (
                entry["story"].get("feature_hint")
                or entry["story"].get("title")
                or "General"
            )
            features.setdefault(feature, []).append(entry["ref"])
        titles = [entry["story"].get("title", "") for entry in items[:2]]
        plan.append(
            {
                "title": _epic_title(hint),
                "summary": (
                    f"{_epic_title(hint)} groups {len(features)} feature(s) and "
                    f"{len(items)} story(ies), including {', '.join(title for title in titles if title)}. "
                    "The stories share the same business outcome and can be reviewed together."
                ),
                "features": [
                    {
                        "title": feature,
                        "summary": "",
                        "story_refs": refs,
                    }
                    for feature, refs in features.items()
                ],
            }
        )
    return plan


def _get_consolidation(
    llm, entries: list[dict], on_event=None
) -> tuple[list[dict], dict, dict]:
    fallback = _fallback_plan(entries)
    if not entries or llm is None:
        return fallback, {}, {}

    system = load_template("consolidate_system")
    template = load_template("consolidate_user")
    user = template.format(
        backlog_input=json.dumps(
            {"stories": _consolidation_payload(entries)}, ensure_ascii=False
        )
    )
    try:
        try:
            raw = llm.complete_json(
                system, user, consolidation_json_schema(), on_event=on_event
            )
        except TypeError as exc:
            if "on_event" not in str(exc):
                raise
            raw = llm.complete_json(system, user, consolidation_json_schema())
        output = validate_consolidation(raw)
    except Exception as exc:
        if on_event:
            on_event(
                "warning",
                f"Consolidation provider failed: {type(exc).__name__}: {exc}",
                {"error": f"{type(exc).__name__}: {exc}"},
            )
        raise

    plan = output.get("epics") or []
    if not plan:
        raise ValueError("Consolidation returned no epics")
    aliases = {
        alias["original"].strip().lower(): alias["canonical"].strip()
        for alias in output.get("persona_aliases") or []
        if alias.get("original") and alias.get("canonical")
    }
    rewrites = {
        rewrite["ref"]: rewrite
        for rewrite in output.get("story_rewrites") or []
        if rewrite.get("ref")
    }
    return plan, aliases, rewrites


def _complete_plan(plan: list[dict], entries: list[dict]) -> list[dict]:
    known = {entry["ref"]: entry for entry in entries}
    assigned: set[str] = set()
    complete = []
    for epic in plan:
        features = []
        for feature in epic.get("features") or []:
            refs = [ref for ref in feature.get("story_refs") or [] if ref in known and ref not in assigned]
            if not refs:
                continue
            assigned.update(refs)
            features.append({**feature, "story_refs": refs})
        if features:
            complete.append({**epic, "features": features})

    missing = [ref for ref in known if ref not in assigned]
    if missing:
        if complete:
            complete[-1].setdefault("features", []).append(
                {
                    "title": "Additional scope",
                    "summary": "",
                    "story_refs": missing,
                }
            )
        else:
            complete = _fallback_plan(entries)
    return complete


def _apply_rewrites(
    story: dict, rewrite: dict | None, aliases: dict[str, str]
) -> dict:
    data = dict(story)
    if rewrite:
        for field in ("title", "persona", "goal", "benefit"):
            value = (rewrite.get(field) or "").strip()
            if value:
                data[field] = value
    persona = (data.get("persona") or data.get("as_a") or "").strip()
    canonical = aliases.get(persona.lower())
    if canonical:
        persona = canonical
    data["persona"] = persona
    data["as_a"] = persona
    data["goal"] = (data.get("goal") or data.get("i_want") or "").strip()
    data["i_want"] = data["goal"]
    data["benefit"] = (data.get("benefit") or data.get("so_that") or "").strip()
    data["so_that"] = data["benefit"]
    return data


def _collect_questions(results: list[GenerationResult]) -> list[dict]:
    found: dict[str, dict] = {}
    for result in results:
        for question in (result.output or {}).get("questions") or []:
            if isinstance(question, str):
                text, priority = question, "Important"
            else:
                text = question.get("text", "")
                priority = question.get("priority", "Important")
            text = _clean_question_text(text)
            if not text:
                continue
            marker = normalize_title(text)
            current = found.get(marker)
            if current is None:
                found[marker] = {
                    "text": text,
                    "priority": priority if priority in _QUESTION_PRIORITY else "Important",
                    "section_id": result.section_id,
                }
            elif _QUESTION_PRIORITY.get(priority, 2) > _QUESTION_PRIORITY.get(
                current["priority"], 2
            ):
                current["priority"] = priority
    return list(found.values())


def consolidate(
    db: Session,
    project: Project,
    results: list[GenerationResult],
    *,
    llm=None,
    on_event=None,
) -> dict:
    sections = {
        section.id: section
        for section in db.scalars(select(Section).where(Section.project_id == project.id))
    }
    existing_items = list(
        db.scalars(select(BacklogItem).where(BacklogItem.project_id == project.id)).all()
    )
    entries = _build_entries(results, sections)
    if not entries:
        return {"epics": 0, "features": 0, "stories": 0, "tests": 0, "merged_stories": 0}

    plan, aliases, rewrites = _get_consolidation(llm, entries, on_event=on_event)
    plan = _complete_plan(plan, entries)
    by_ref = {entry["ref"]: entry for entry in entries}

    epics: list[BacklogItem] = []
    features: list[BacklogItem] = []
    stories: list[BacklogItem] = []
    tests: list[BacklogItem] = []

    for epic_plan in plan:
        refs = [
            ref
            for feature in epic_plan.get("features") or []
            for ref in feature.get("story_refs") or []
        ]
        epic_sections = _unique(
            [
                section_id
                for ref in refs
                if ref in by_ref
                for section_id in by_ref[ref]["source_sections"]
            ]
        )
        epic = BacklogItem(
            project_id=project.id,
            kind="epic",
            source_section_id=epic_sections[0] if epic_sections else "",
            source_sections=epic_sections,
            title=epic_plan.get("title", "").strip() or "Project scope",
            body={
                "summary": epic_plan.get("summary", "").strip(),
                "feature_count": len(epic_plan.get("features") or []),
                "story_count": len(refs),
            },
            status="proposed",
        )
        db.add(epic)
        db.flush()
        epics.append(epic)

        for feature_plan in epic_plan.get("features") or []:
            feature_refs = [
                ref for ref in feature_plan.get("story_refs") or [] if ref in by_ref
            ]
            if not feature_refs:
                continue
            feature_sections = _unique(
                [
                    section_id
                    for ref in feature_refs
                    for section_id in by_ref[ref]["source_sections"]
                ]
            )
            feature = BacklogItem(
                project_id=project.id,
                kind="feature",
                parent_item_id=epic.id,
                source_section_id=feature_sections[0] if feature_sections else "",
                source_sections=feature_sections,
                title=feature_plan.get("title", "").strip() or "General feature",
                body={"summary": feature_plan.get("summary", "").strip()},
                status="proposed",
            )
            db.add(feature)
            db.flush()
            features.append(feature)

            for ref in feature_refs:
                entry = by_ref[ref]
                data = _apply_rewrites(
                    entry["story"], rewrites.get(ref), aliases
                )
                body = {
                    key: value
                    for key, value in data.items()
                    if key not in ("tests",)
                }
                body["acceptance_criteria"] = _unique(
                    body.get("acceptance_criteria") or []
                )[:5]
                body.update(
                    {
                        "section_id": entry["section_id"],
                        "feature_title": feature.title,
                        "epic_title": epic.title,
                        "merged_from": _unique(
                            list(entry["source_sections"])
                            + (body.get("merged_from") or [])
                        ),
                    }
                )
                story = BacklogItem(
                    project_id=project.id,
                    kind="story",
                    parent_item_id=feature.id,
                    source_section_id=entry["section_id"],
                    source_sections=entry["source_sections"],
                    title=data.get("title", "").strip() or "Untitled story",
                    body=body,
                    status="proposed",
                )
                db.add(story)
                db.flush()
                stories.append(story)

                for test_data in entry["tests"][:3]:
                    test = BacklogItem(
                        project_id=project.id,
                        kind="test",
                        parent_item_id=story.id,
                        source_section_id=entry["section_id"],
                        source_sections=entry["source_sections"],
                        title=test_data.get("title", "").strip() or "Test case",
                        body={
                            **test_data,
                            "section_id": entry["section_id"],
                        },
                        status="proposed",
                    )
                    db.add(test)
                    tests.append(test)

    db.flush()

    epic_number = _next_number(existing_items, "epic")
    for epic in epics:
        epic.key = f"EP-{epic_number:02d}"
        epic_number += 1
    feature_number = _next_number(existing_items, "feature")
    for feature in features:
        feature.key = f"FT-{feature_number:02d}"
        feature_number += 1
    story_number = _next_number(existing_items, "story")
    story_by_id = {}
    for story in stories:
        story.key = f"US-{story_number:03d}"
        story_number += 1
        story_by_id[story.id] = story
    test_number = _next_number(existing_items, "test")
    for test in tests:
        test.key = f"TC-{test_number:03d}"
        test_number += 1
        parent = story_by_id.get(test.parent_item_id)
        if parent:
            test.body = {**(test.body or {}), "story_key": parent.key}

    existing_questions = list(
        db.scalars(select(Question).where(Question.project_id == project.id)).all()
    )
    question_by_text = {normalize_title(item.text): item for item in existing_questions}
    for question in _collect_questions(results):
        marker = normalize_title(question["text"])
        current = question_by_text.get(marker)
        if current:
            if _QUESTION_PRIORITY.get(question["priority"], 2) > _QUESTION_PRIORITY.get(
                current.priority, 2
            ):
                current.priority = question["priority"]
            continue
        item = Question(
            project_id=project.id,
            section_id=question["section_id"],
            text=question["text"],
            priority=question["priority"],
            status="open",
        )
        db.add(item)
        question_by_text[marker] = item

    db.commit()
    return {
        "epics": len(epics),
        "features": len(features),
        "stories": len(stories),
        "tests": len(tests),
        "merged_stories": sum(
            1 for entry in entries if len(entry["source_sections"]) > 1
        ),
    }
