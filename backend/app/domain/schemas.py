from datetime import datetime

from pydantic import BaseModel, Field


class ProjectOut(BaseModel):
    id: str
    name: str
    status: str
    error: str | None = None
    checklist: dict = Field(default_factory=dict)
    context_approved: bool = False
    created_at: datetime | None = None
    model_config = {"from_attributes": True}


class DocumentOut(BaseModel):
    id: str
    project_id: str
    version: int
    filename: str
    stats: dict = Field(default_factory=dict)
    warnings: list = Field(default_factory=list)
    checklist: dict = Field(default_factory=dict)
    created_at: datetime | None = None
    model_config = {"from_attributes": True}


class SectionOut(BaseModel):
    id: str
    project_id: str
    parent_id: str | None
    number: str
    title: str
    text: str
    level: int
    position: int
    is_leaf: bool
    role: str
    lineage: list[str] = Field(default_factory=list)
    model_config = {"from_attributes": True}


class SectionPatch(BaseModel):
    role: str | None = None
    title: str | None = None


class LinkOut(BaseModel):
    id: int
    project_id: str
    source_id: str
    target_id: str
    kind: str
    score: float
    reason: str = ""
    enabled: bool = True
    model_config = {"from_attributes": True}


class LinkCreate(BaseModel):
    source_id: str
    target_id: str
    kind: str = "manual"
    score: float = 1.0
    reason: str = "manual link"
    enabled: bool = True


class LinkPatch(BaseModel):
    enabled: bool | None = None
    reason: str | None = None
    score: float | None = None


class ContextOut(BaseModel):
    section_id: str
    section: dict = Field(default_factory=dict)
    context: dict = Field(default_factory=dict)
    prompt: str = ""
    links: list = Field(default_factory=list)


class BacklogItemOut(BaseModel):
    id: str
    project_id: str
    key: str
    kind: str
    parent_item_id: str | None = None
    source_section_id: str
    source_sections: list = Field(default_factory=list)
    title: str
    body: dict = Field(default_factory=dict)
    status: str
    confidence: float = 0.0
    questions: list = Field(default_factory=list)
    model_config = {"from_attributes": True}


class ItemPatch(BaseModel):
    title: str | None = None
    body: dict | None = None
    status: str | None = None
    by: str = "ba"


class ItemRegenerate(BaseModel):
    instruction: str = ""
    by: str = "ba"


class QuestionOut(BaseModel):
    id: str
    project_id: str
    section_id: str
    text: str
    answer: str = ""
    status: str
    created_at: datetime | None = None
    model_config = {"from_attributes": True}


class QuestionPatch(BaseModel):
    answer: str | None = None
    status: str | None = None


class AskRequest(BaseModel):
    question: str


class AskCitation(BaseModel):
    section_id: str
    number: str = ""
    title: str = ""
    score: float = 0.0
    snippet: str = ""


class AskResponse(BaseModel):
    answer: str
    citations: list[AskCitation] = Field(default_factory=list)
