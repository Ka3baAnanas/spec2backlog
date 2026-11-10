import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def _id() -> str:
    return uuid.uuid4().hex


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(30), default="created")
    # created -> ingested -> graph_built -> generated -> validated -> exported
    checklist: Mapped[dict] = mapped_column(JSON, default=dict)  # expected sections found/missing
    nodes: Mapped[list["Node"]] = relationship(back_populates="project", cascade="all,delete")


class Node(Base):
    """A tree node. Leaves carry text; inner nodes are headings. Replaces separate nodes/edges for the tree."""
    __tablename__ = "nodes"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)  # = text_id
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    parent_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    number: Mapped[str] = mapped_column(String(30), default="")  # "4.1"
    title: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text, default="")
    level: Mapped[int] = mapped_column(Integer, default=0)
    position: Mapped[int] = mapped_column(Integer, default=0)
    is_leaf: Mapped[bool] = mapped_column(default=False)
    is_global: Mapped[bool] = mapped_column(default=False)  # glossary / context: sent with every prompt
    is_front_matter: Mapped[bool] = mapped_column(default=False)  # TOC / version history: never generated
    lineage: Mapped[list] = mapped_column(JSON, default=list)
    project: Mapped[Project] = relationship(back_populates="nodes")


class Edge(Base):
    """Meaning-graph edge between two leaves (the tree itself lives in Node.parent_id)."""
    __tablename__ = "edges"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    source_id: Mapped[str] = mapped_column(String(32), index=True)
    target_id: Mapped[str] = mapped_column(String(32))
    kind: Mapped[str] = mapped_column(String(20))  # similarity | reference
    score: Mapped[float] = mapped_column(Float, default=1.0)


class ItemStatus(str, enum.Enum):
    proposed = "proposed"
    approved = "approved"
    edited = "edited"
    rejected = "rejected"


class BacklogItem(Base):
    __tablename__ = "backlog_items"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    source_node_id: Mapped[str] = mapped_column(String(32), index=True)  # traceability
    kind: Mapped[str] = mapped_column(String(20))  # epic | story | test
    parent_item_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[dict] = mapped_column(JSON, default=dict)  # criteria, steps, priority...
    status: Mapped[ItemStatus] = mapped_column(Enum(ItemStatus), default=ItemStatus.proposed)
    questions: Mapped[list] = mapped_column(JSON, default=list)  # gaps => questions for the client


class ValidationEvent(Base):
    __tablename__ = "validation_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[str] = mapped_column(ForeignKey("backlog_items.id"), index=True)
    action: Mapped[str] = mapped_column(String(20))
    before: Mapped[dict] = mapped_column(JSON, default=dict)
    after: Mapped[dict] = mapped_column(JSON, default=dict)
    by: Mapped[str] = mapped_column(String(100), default="ba")
    at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RunEvent(Base):
    """Append-only pipeline journal used by the UI (SSE replay + live progress)."""

    __tablename__ = "run_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    stage: Mapped[str] = mapped_column(String(20), index=True)  # ingestion|tree|graph|generation|export
    type: Mapped[str] = mapped_column(String(20))  # stage_start|stage_end|progress|leaf_*|link_found|warning|error
    message: Mapped[str] = mapped_column(Text, default="")
    data: Mapped[dict] = mapped_column(JSON, default=dict)


class GenerationTrace(Base):
    """Exact LLM input/output for one leaf, including retries and created items."""

    __tablename__ = "generation_traces"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    node_id: Mapped[str] = mapped_column(String(32), index=True)
    prompt: Mapped[str] = mapped_column(Text, default="")
    response_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    neighbours: Mapped[list] = mapped_column(JSON, default=list)
    global_context_ids: Mapped[list] = mapped_column(JSON, default=list)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="ok")  # ok|failed|retried
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    items_created: Mapped[dict] = mapped_column(JSON, default=dict)
