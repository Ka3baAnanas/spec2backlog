"""Pydantic schemas for the two-pass generation pipeline."""

import json

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.generation.normalize import normalize_benefit, normalize_goal

PRIORITIES = {"must", "should", "could"}
ESTIMATES = {"S", "M", "L"}
QUESTION_PRIORITIES = {"Blocking", "Important", "Minor"}


def _text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _text_items(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, dict):
        text = value.get("text") or value.get("question") or value.get("step")
        return [_text(text or json.dumps(value))]
    if isinstance(value, (list, tuple)):
        out: list[str] = []
        for item in value:
            if isinstance(item, str):
                if item.strip():
                    out.append(item.strip())
            elif isinstance(item, dict):
                text = item.get("text") or item.get("question") or item.get("step")
                out.append(_text(text if text is not None else json.dumps(item)))
            elif item is not None:
                out.append(_text(item))
        return [item for item in out if item]
    return [_text(value)]


class TestCase(BaseModel):
    title: str = ""
    preconditions: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    test_data: str = ""
    expected: str = ""

    @field_validator("title", "test_data", "expected", mode="before")
    @classmethod
    def _text_fields(cls, value):
        return _text(value)

    @field_validator("preconditions", "steps", mode="before")
    @classmethod
    def _lists(cls, value):
        return _text_items(value)


class Story(BaseModel):
    title: str = ""
    persona: str = ""
    goal: str = ""
    benefit: str = ""
    as_a: str = ""
    i_want: str = ""
    so_that: str = ""
    description: str = ""
    business_rules: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    priority: str = "should"
    priority_reason: str = ""
    estimate: str = "M"
    dependencies: list[str] = Field(default_factory=list)
    tests: list[TestCase] = Field(default_factory=list)
    feature_hint: str = ""
    source_evidence: list[str] = Field(default_factory=list)
    ambiguity_flag: bool = False

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, value):
        if not isinstance(value, dict):
            value = {"title": value}
        data = dict(value)
        persona = _text(data.get("persona") or data.get("as_a"))
        goal = normalize_goal(_text(data.get("goal") or data.get("i_want")))
        benefit = normalize_benefit(_text(data.get("benefit") or data.get("so_that")))
        data["persona"] = persona
        data["goal"] = goal
        data["benefit"] = benefit
        data["as_a"] = _text(data.get("as_a") or persona)
        data["i_want"] = _text(data.get("i_want") or goal)
        data["so_that"] = _text(data.get("so_that") or benefit)
        data["title"] = _text(data.get("title"))
        data["description"] = _text(data.get("description") or data.get("summary"))
        data["feature_hint"] = _text(
            data.get("feature_hint") or data.get("feature") or data.get("feature_name")
        )
        data["priority_reason"] = _text(
            data.get("priority_reason") or data.get("priority_rationale") or data.get("why")
        )
        data["business_rules"] = _text_items(
            data.get("business_rules") or data.get("rules") or data.get("businessRules")
        )
        data["acceptance_criteria"] = _text_items(
            data.get("acceptance_criteria") or data.get("criteria") or data.get("ac")
        )
        data["dependencies"] = _text_items(data.get("dependencies"))
        data["source_evidence"] = _text_items(
            data.get("source_evidence") or data.get("evidence") or data.get("sources")
        )
        tests = data.get("tests") or data.get("test_cases") or []
        data["tests"] = tests if isinstance(tests, list) else []
        priority = _text(data.get("priority")).lower()
        data["priority"] = priority if priority in PRIORITIES else "should"
        estimate = _text(data.get("estimate")).upper()
        data["estimate"] = estimate if estimate in ESTIMATES else "M"
        data["ambiguity_flag"] = bool(data.get("ambiguity_flag") or data.get("ambiguous"))
        return data

    @field_validator("title", "persona", "goal", "benefit", "as_a", "i_want", "so_that",
                     "description", "priority_reason", "feature_hint", mode="before")
    @classmethod
    def _text_fields(cls, value):
        return _text(value)

    @field_validator("business_rules", "acceptance_criteria", "dependencies",
                     "source_evidence", mode="before")
    @classmethod
    def _lists(cls, value):
        return _text_items(value)

    @field_validator("estimate", mode="before")
    @classmethod
    def _estimate(cls, value):
        estimate = _text(value).upper()
        return estimate if estimate in ESTIMATES else "M"

    @field_validator("priority", mode="before")
    @classmethod
    def _priority(cls, value):
        priority = _text(value).lower()
        return priority if priority in PRIORITIES else "should"


class Question(BaseModel):
    text: str = ""
    priority: str = "Important"

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, value):
        if isinstance(value, str):
            return {"text": value, "priority": "Important"}
        if isinstance(value, dict):
            data = dict(value)
            data["text"] = _text(
                data.get("text") or data.get("question") or data.get("label")
            )
            priority = _text(data.get("priority") or "Important").capitalize()
            data["priority"] = priority if priority in QUESTION_PRIORITIES else "Important"
            return data
        return {"text": _text(value), "priority": "Important"}

    @field_validator("text", mode="before")
    @classmethod
    def _text_field(cls, value):
        return _text(value)

    @field_validator("priority", mode="before")
    @classmethod
    def _priority(cls, value):
        priority = _text(value or "Important").capitalize()
        return priority if priority in QUESTION_PRIORITIES else "Important"


class Epic(BaseModel):
    title: str = ""

    @field_validator("title", mode="before")
    @classmethod
    def _title_text(cls, value):
        return _text(value)


class GenerationOutput(BaseModel):
    epic: Epic | None = None
    stories: list[Story] = Field(default_factory=list)
    questions: list[Question] = Field(default_factory=list)

    @field_validator("epic", mode="before")
    @classmethod
    def _epic(cls, value):
        if value is None:
            return None
        if isinstance(value, str):
            return {"title": value}
        return value

    @field_validator("stories", mode="before")
    @classmethod
    def _stories(cls, value):
        return value or []

    @field_validator("questions", mode="before")
    @classmethod
    def _questions(cls, value):
        return value or []


class ConsolidationFeature(BaseModel):
    title: str = ""
    summary: str = ""
    story_refs: list[str] = Field(default_factory=list)

    @field_validator("title", "summary", mode="before")
    @classmethod
    def _text_fields(cls, value):
        return _text(value)

    @field_validator("story_refs", mode="before")
    @classmethod
    def _refs(cls, value):
        if isinstance(value, str):
            value = [value]
        return [_text(item) for item in (value or []) if _text(item)]


class ConsolidationEpic(BaseModel):
    title: str = ""
    summary: str = ""
    features: list[ConsolidationFeature] = Field(default_factory=list)

    @field_validator("title", "summary", mode="before")
    @classmethod
    def _text_fields(cls, value):
        return _text(value)

    @field_validator("features", mode="before")
    @classmethod
    def _features(cls, value):
        return value or []


class PersonaAlias(BaseModel):
    original: str = ""
    canonical: str = ""

    @field_validator("original", "canonical", mode="before")
    @classmethod
    def _text_fields(cls, value):
        return _text(value)


class StoryRewrite(BaseModel):
    ref: str = ""
    title: str = ""
    persona: str = ""
    goal: str = ""
    benefit: str = ""

    @field_validator("ref", "title", "persona", "goal", "benefit", mode="before")
    @classmethod
    def _text_fields(cls, value):
        return _text(value)


class ConsolidationOutput(BaseModel):
    epics: list[ConsolidationEpic] = Field(default_factory=list)
    persona_aliases: list[PersonaAlias] = Field(default_factory=list)
    story_rewrites: list[StoryRewrite] = Field(default_factory=list)

    @field_validator("epics", "persona_aliases", "story_rewrites", mode="before")
    @classmethod
    def _lists(cls, value):
        return value or []


def output_json_schema() -> dict:
    return GenerationOutput.model_json_schema()


def consolidation_json_schema() -> dict:
    return ConsolidationOutput.model_json_schema()


def validate_output(raw) -> dict:
    if not isinstance(raw, dict) or not raw:
        raise ValueError("LLM response must be a non-empty JSON object")
    data = dict(raw)
    top_tests = data.pop("tests", None)
    stories = data.get("stories") or []
    if top_tests and stories:
        stories[0] = {**stories[0], "tests": top_tests}
        data["stories"] = stories
    return GenerationOutput.model_validate(data).model_dump()


def validate_consolidation(raw) -> dict:
    if not isinstance(raw, dict) or not raw:
        raise ValueError("LLM consolidation response must be a non-empty JSON object")
    return ConsolidationOutput.model_validate(raw).model_dump()


def empty_counts() -> dict:
    return {"epics": 0, "features": 0, "stories": 0, "tests": 0, "questions": 0}
