"""Ingestion orchestration: parse -> structure -> link ("prepare") and persistence."""

import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.events import emit
from app.domain.models import (
    BacklogItem,
    ContextPack,
    Document,
    GenerationTrace,
    GlossaryTerm,
    Link,
    Project,
    Question,
    Section,
)
from app.modules.ingestion import quality
from app.modules.ingestion.parsers.docx import extract_docx
from app.modules.ingestion.parsers.pdf import extract_pdf
from app.modules.ingestion.pivot import PivotDocument
from app.modules.knowledge.service import clear_knowledge, prepare_knowledge
from app.modules.structure.service import structure_nodes


def to_pivot(path: Path) -> PivotDocument:
    extension = path.suffix.lower()
    if extension == ".docx":
        return extract_docx(path)
    if extension == ".pdf":
        return extract_pdf(path)
    raise ValueError(f"Unsupported file type: {extension or '(none)'}; expected .docx or .pdf")


def _clear_derived(db: Session, project_id: str) -> None:
    for model in (Link, GlossaryTerm, ContextPack, BacklogItem, Question, GenerationTrace):
        db.query(model).filter(model.project_id == project_id).delete(synchronize_session=False)
    db.query(Section).filter(
        Section.project_id == project_id, Section.source != "manual"
    ).delete(synchronize_session=False)
    db.flush()


def _emit_ingestion(project_id: str, pivot: PivotDocument, doc_stats: dict) -> None:
    emit(project_id, "ingestion", "stage_start", "Ingestion started", doc_stats)
    emit(
        project_id,
        "ingestion",
        "progress",
        (f"Extracted {doc_stats['headings']} headings, {doc_stats['paragraphs']} paragraphs, "
         f"{doc_stats['tables']} tables, {doc_stats['list_items']} list items"),
        doc_stats,
    )
    for warning in pivot.warnings:
        emit(project_id, "ingestion", "warning", warning, {"warning": warning})
    emit(project_id, "ingestion", "stage_end", "Ingestion finished", doc_stats)


def _emit_structure(project_id: str, nodes: list) -> None:
    data = {
        "sections": len(nodes),
        "requirements": sum(1 for node in nodes if node.role == "requirement"),
        "context": sum(1 for node in nodes if node.role == "context"),
        "glossary": sum(1 for node in nodes if node.role == "glossary"),
        "ignored": sum(1 for node in nodes if node.role == "ignored"),
        "front_matter": sum(1 for node in nodes if node.role == "front_matter"),
        "max_depth": max((node.level for node in nodes), default=0),
    }
    emit(project_id, "structure", "stage_start", "Building document structure", data)
    emit(
        project_id,
        "structure",
        "progress",
        f"{data['sections']} sections, {data['requirements']} requirement leaves",
        data,
    )
    emit(project_id, "structure", "stage_end", "Structure ready", data)


def prepare_project(
    db: Session, project: Project, path: Path, filename: str | None = None
) -> dict:
    """Run parse, structure and link, then stop at the human context checkpoint."""
    project_id = project.id
    emit(project_id, "ingestion", "stage_start", "Preparing specification", {})
    pivot = to_pivot(path)  # may raise ValueError for unsupported files
    if filename:
        pivot.source = filename
    doc_stats = quality.stats(pivot)
    doc_warnings = quality.warnings(pivot)
    doc_checklist = quality.checklist(pivot)

    _clear_derived(db, project_id)
    clear_knowledge(project_id)

    last = db.scalars(
        select(Document)
        .where(Document.project_id == project_id)
        .order_by(Document.version.desc())
    ).first()
    document = Document(
        project_id=project_id,
        version=(last.version + 1) if last else 1,
        filename=filename or path.name,
        path=str(path),
        stats={
            **doc_stats,
            "preview": quality.pivot_preview(pivot),
            "document_blocks": quality.document_blocks(pivot),
            "skipped_lines": list(pivot.skipped),
        },
        warnings=doc_warnings,
        checklist=doc_checklist,
    )
    db.add(document)
    project.status = "parsed"
    project.checklist = doc_checklist
    project.context_approved = False
    project.error = None
    db.commit()
    db.query(Section).filter(
        Section.project_id == project_id, Section.source == "manual"
    ).update({Section.document_id: document.id}, synchronize_session=False)
    db.commit()
    _emit_ingestion(project_id, pivot, doc_stats)

    nodes = structure_nodes(pivot, lambda: uuid.uuid4().hex)
    for position, node in enumerate(nodes):
        db.add(
            Section(
                id=node.id,
                project_id=project_id,
                document_id=document.id,
                parent_id=node.parent,
                number=node.number,
                title=node.title,
                text=node.text,
                level=node.level,
                position=position,
                is_leaf=node.is_leaf and bool(node.text.strip()),
                role=node.role,
                lineage=node.lineage,
            )
        )
    root_id = next((node.id for node in nodes if node.parent is None), None)
    if root_id:
        db.query(Section).filter(
            Section.project_id == project_id, Section.source == "manual"
        ).update({Section.parent_id: root_id}, synchronize_session=False)
    project.status = "structured"
    db.commit()
    _emit_structure(project_id, nodes)

    knowledge = prepare_knowledge(db, project)
    project = db.get(Project, project_id)
    project.status = "linked"
    db.commit()

    project.status = "awaiting_context_approval"
    db.commit()
    emit(
        project_id,
        "context",
        "info",
        "Context ready - waiting for human approval",
        {"links": knowledge["links"], "glossary_terms": knowledge["glossary_terms"]},
    )
    return {
        "document_id": document.id,
        "document_version": document.version,
        "sections": len(nodes),
        "links": knowledge["links"],
        "glossary_terms": knowledge["glossary_terms"],
        "status": project.status,
    }
