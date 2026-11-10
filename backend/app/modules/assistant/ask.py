"""Ask the spec: simple extractive RAG with citations to sections."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import Project, Section
from app.modules.knowledge.retriever import retrieve_citations


def answer_question(db: Session, project: Project, question: str, top_k: int = 4) -> dict:
    sections = list(
        db.scalars(
            select(Section)
            .where(Section.project_id == project.id)
            .order_by(Section.position)
        ).all()
    )
    citations = retrieve_citations(project.id, question, sections, top_k=top_k)
    if not citations:
        return {
            "answer": "I could not find a relevant section in this specification.",
            "citations": [],
        }

    best = citations[0]
    label = f"section {best['number']}" if best["number"] else f"'{best['title']}'"
    answer = f"According to {label} ({best['title']}): {best['snippet']}"
    if len(citations) > 1:
        answer += "\n\nRelated sections: " + "; ".join(
            f"{item['number'] or item['title']} - {item['title']}" for item in citations[1:]
        )

    return {
        "answer": answer,
        "citations": [
            {
                "section_id": item["section_id"],
                "number": item["number"],
                "title": item["title"],
                "score": item["score"],
                "snippet": item["snippet"],
            }
            for item in citations
        ],
    }
