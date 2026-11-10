"""Pydantic output schema for one generation call."""

from pydantic import BaseModel, Field, field_validator


class Epic(BaseModel):
    title: str = ""


class Story(BaseModel):
    title: str = ""
    as_a: str = ""
    i_want: str = ""
    so_that: str = ""
    acceptance_criteria: list[str] = Field(default_factory=list)
    priority: str = "should"

    @field_validator("acceptance_criteria", mode="before")
    @classmethod
    def _criteria_list(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return value


class TestCase(BaseModel):
    title: str = ""
    steps: list[str] = Field(default_factory=list)
    expected: str = ""
    story_title: str = ""

    @field_validator("steps", mode="before")
    @classmethod
    def _steps_list(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return value


class GenerationOutput(BaseModel):
    epic: Epic | None = None
    stories: list[Story] = Field(default_factory=list)
    tests: list[TestCase] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)

    @field_validator("stories", "tests", "questions", mode="before")
    @classmethod
    def _list_values(cls, value):
        return value or []


def output_json_schema() -> dict:
    return GenerationOutput.model_json_schema()


def validate_output(raw) -> dict:
    if not isinstance(raw, dict) or not raw:
        raise ValueError("LLM response must be a non-empty JSON object")
    return GenerationOutput.model_validate(raw).model_dump()


def empty_counts() -> dict:
    return {"epics": 0, "stories": 0, "tests": 0, "questions": 0}
