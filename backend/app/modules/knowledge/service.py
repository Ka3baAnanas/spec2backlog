"""Knowledge service: build hybrid links + glossary, persist them."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import GlossaryTerm, Link, Project, Section
from app.modules.knowledge.glossary import extract_glossary
from app.modules.knowledge.retriever import retrieve_links
from app.modules.knowledge.vector_store import get_store


def prepare_knowledge(db: Session, project: Project) -> dict:
    project_id = project.id
    sections = db.scalars(
        select(Section).where(Section.project_id == project_id).order_by(Section.position)
    ).all()

    db.query(Link).filter(Link.project_id == project_id).delete(synchronize_session=False)
    db.query(GlossaryTerm).filter(GlossaryTerm.project_id == project_id).delete(
        synchronize_session=False
    )
    db.commit()  # release the write lock before emitting events from retrieval

    links = retrieve_links(project_id, sections)
    for link in links:
        db.add(Link(project_id=project_id, **link))

    terms = extract_glossary(sections)
    for term in terms:
        db.add(GlossaryTerm(project_id=project_id, **term))

    db.commit()
    return {"links": len(links), "glossary_terms": len(terms)}


def clear_knowledge(project_id: str) -> None:
    get_store().delete_project(project_id)
