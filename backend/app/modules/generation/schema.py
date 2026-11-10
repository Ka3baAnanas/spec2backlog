"""Pydantic output schema for one generation call."""

import json

from pydantic import BaseModel, Field, field_validator


def _text_items(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [str(value.get("text") or value.get("question") or json.dumps(value))]
    if isinstance(value, (list, tuple)):
        out: list[str] = []
        for item in value:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("question") or item.get("step")
                out.append(str(text) if text is not None else json.dumps(item))
            elif item is not None:
                out.append(str(item))
        return out
    return [str(value)]


class Epic(BaseModel):
    title: str = ""

    @field_validator("title", mode="before")
    @classmethod
    def _title_text(cls, value):
        return "" if value is None else str(value)


class Story(BaseModel):
    title: str = ""
    as_a: str = ""
    i_want: str = ""
    so_that: str = ""
    acceptance_criteria: list[str] = Field(default_factory=list)
    priority: str = "should"

    @field_validator("title", "as_a", "i_want", "so_that", "priority", mode="before")
    @classmethod
    def _text(cls, value):
        return "" if value is None else str(value)

    @field_validator("acceptance_criteria", mode="before")
    @classmethod
    def _criteria_list(cls, value):
        return _text_items(value)


class TestCase(BaseModel):
    title: str = ""
    steps: list[str] = Field(default_factory=list)
    expected: str = ""
    story_title: str = ""

    @field_validator("title", "expected", "story_title", mode="before")
    @classmethod
    def _text(cls, value):
        return "" if value is None else str(value)

    @field_validator("steps", mode="before")
    @classmethod
    def _steps_list(cls, value):
        return _text_items(value)


class GenerationOutput(BaseModel):
    epic: Epic | None = None
    stories: list[Story] = Field(default_factory=list)
    tests: list[TestCase] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)

    @field_validator("epic", mode="before")
    @classmethod
    def _epic(cls, value):
        if value is None:
            return None
        if isinstance(value, str):
            return {"title": value}
        return value

    @field_validator("stories", "tests", mode="before")
    @classmethod
    def _list_values(cls, value):
        return value or []

    @field_validator("questions", mode="before")
    @classmethod
    def _questions(cls, value):
        return _text_items(value)


def output_json_schema() -> dict:
    return GenerationOutput.model_json_schema()


def validate_output(raw) -> dict:
    if not isinstance(raw, dict) or not raw:
        raise ValueError("LLM response must be a non-empty JSON object")
    return GenerationOutput.model_validate(raw).model_dump()


def empty_counts() -> dict:
    return {"epics": 0, "stories": 0, "tests": 0, "questions": 0}
