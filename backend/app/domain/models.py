import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.domain.enums import (
    ItemKind,
    ItemStatus,
    LinkKind,
    PipelineState,
    QuestionStatus,
    SectionRole,
)


def _id() -> str:
    return uuid.uuid4().hex


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(40), default=PipelineState.uploaded.value)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    checklist: Mapped[dict] = mapped_column(JSON, default=dict)
    context_approved: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Document(Base):
    """One uploaded version of the specification."""

    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    filename: Mapped[str] = mapped_column(String(400), default="")
    path: Mapped[str | None] = mapped_column(Text, nullable=True)
    stats: Mapped[dict] = mapped_column(JSON, default=dict)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    checklist: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Section(Base):
    """A tree node. Leaves carry text; inner nodes are headings."""

    __tablename__ = "sections"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    parent_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    number: Mapped[str] = mapped_column(String(30), default="")
    title: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text, default="")
    level: Mapped[int] = mapped_column(Integer, default=0)
    position: Mapped[int] = mapped_column(Integer, default=0)
    is_leaf: Mapped[bool] = mapped_column(default=False)
    role: Mapped[str] = mapped_column(String(20), default=SectionRole.requirement.value)
    lineage: Mapped[list] = mapped_column(JSON, default=list)


class Link(Base):
    """A link between two sections (hybrid retrieval or manual)."""

    __tablename__ = "links"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    source_id: Mapped[str] = mapped_column(String(32), index=True)
    target_id: Mapped[str] = mapped_column(String(32), index=True)
    kind: Mapped[str] = mapped_column(String(20), default=LinkKind.similarity.value)
    score: Mapped[float] = mapped_column(Float, default=1.0)
    reason: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(default=True)


class GlossaryTerm(Base):
    __tablename__ = "glossary_terms"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    term: Mapped[str] = mapped_column(String(200))
    definition: Mapped[str] = mapped_column(Text, default="")
    kind: Mapped[str] = mapped_column(String(20), default="term")
    source_section_id: Mapped[str | None] = mapped_column(String(32), nullable=True)


class ContextPack(Base):
    """Snapshot of the rendered prompt for one section."""

    __tablename__ = "context_packs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    section_id: Mapped[str] = mapped_column(String(32), index=True)
    prompt: Mapped[str] = mapped_column(Text, default="")
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BacklogItem(Base):
    __tablename__ = "backlog_items"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    key: Mapped[str] = mapped_column(String(20), default="")
    kind: Mapped[str] = mapped_column(String(20), default=ItemKind.story.value)
    parent_item_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    source_section_id: Mapped[str] = mapped_column(String(32), index=True)
    source_sections: Mapped[list] = mapped_column(JSON, default=list)
    title: Mapped[str] = mapped_column(Text, default="")
    body: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default=ItemStatus.proposed.value)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    questions: Mapped[list] = mapped_column(JSON, default=list)


class Question(Base):
    __tablename__ = "questions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    section_id: Mapped[str] = mapped_column(String(32), index=True)
    text: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default=QuestionStatus.open.value)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class GenerationTrace(Base):
    """Exact LLM input/output for one section, including retries."""

    __tablename__ = "generation_traces"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    section_id: Mapped[str] = mapped_column(String(32), index=True)
    prompt: Mapped[str] = mapped_column(Text, default="")
    response_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    links: Mapped[list] = mapped_column(JSON, default=list)
    global_context_ids: Mapped[list] = mapped_column(JSON, default=list)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="ok")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    items_created: Mapped[dict] = mapped_column(JSON, default=dict)


class RunEvent(Base):
    """Append-only pipeline journal used by the UI (SSE replay + live progress)."""

    __tablename__ = "run_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    stage: Mapped[str] = mapped_column(String(20), index=True)
    type: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(Text, default="")
    data: Mapped[dict] = mapped_column(JSON, default=dict)


class ReviewEvent(Base):
    __tablename__ = "review_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    item_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(30))
    before: Mapped[dict] = mapped_column(JSON, default=dict)
    after: Mapped[dict] = mapped_column(JSON, default=dict)
    by: Mapped[str] = mapped_column(String(100), default="ba")
    at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
