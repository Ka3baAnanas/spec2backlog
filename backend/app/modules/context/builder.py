"""Context pack builder: the single function used by both preview and generation."""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.domain.enums import SectionRole
from app.domain.models import ContextPack, GlossaryTerm, Link, Section
from app.modules.context.budget import estimate_tokens, fit_sections, truncate_text
from app.modules.generation.prompts import load_template


def _section_dict(section: Section) -> dict:
    return {
        "section_id": section.id,
        "number": section.number,
        "title": section.title,
        "text": section.text,
        "role": section.role,
        "lineage": section.lineage or [],
    }


def _enabled_links(db: Session, section: Section) -> list[Link]:
    return list(
        db.scalars(
            select(Link).where(
                Link.project_id == section.project_id,
                Link.enabled.is_(True),
                or_(Link.source_id == section.id, Link.target_id == section.id),
            )
        ).all()
    )


def build_context(db: Session, section: Section) -> dict:
    section_id = section.id
    project_id = section.project_id
    links = _enabled_links(db, section)
    linked_ids = {
        link.target_id if link.source_id == section_id else link.source_id for link in links
    }
    linked_ids.discard(section_id)

    linked_sections = []
    if linked_ids:
        linked_sections = list(
            db.scalars(select(Section).where(Section.id.in_(linked_ids))).all()
        )
    linked_sections = [
        item for item in linked_sections
        if item.role not in (SectionRole.front_matter.value, SectionRole.ignored.value)
    ]
    linked_sections.sort(key=lambda item: (item.number or "~", item.position))
    linked_payload = [_section_dict(item) for item in linked_sections]

    global_sections = list(
        db.scalars(
            select(Section).where(
                Section.project_id == project_id,
                Section.role == SectionRole.context.value,
                Section.id != section_id,
            )
        ).all()
    )
    global_sections.sort(key=lambda item: item.position)
    global_payload = [_section_dict(item) for item in global_sections]

    glossary_terms = list(
        db.scalars(
            select(GlossaryTerm).where(GlossaryTerm.project_id == project_id)
        ).all()
    )
    glossary_payload = [
        {"term": term.term, "definition": term.definition, "kind": term.kind}
        for term in glossary_terms
    ]

    budget = settings.context_max_tokens
    kept_global, dropped_global = fit_sections(global_payload, budget)
    remaining = max(0, budget - sum(estimate_tokens(item["text"]) for item in kept_global))
    kept_links, dropped_links = fit_sections(linked_payload, remaining)

    return {
        "section": _section_dict(section),
        "lineage": section.lineage or [],
        "text": section.text,
        "links": linked_payload,
        "linked_sections": kept_links,
        "global_context": kept_global,
        "glossary": glossary_payload,
        "dropped": {
            "linked_sections": [item["section_id"] for item in dropped_links],
            "global_context": [item["section_id"] for item in dropped_global],
        },
        "budget": {"max_tokens": budget},
    }


def render_prompt(context: dict) -> str:
    global_context = "\n\n".join(
        f"[{item['number']} {item['title']}]\n{item['text']}"
        for item in context.get("global_context", [])
    ) or "(none)"
    glossary = "\n".join(
        f"- {item['term']}: {item['definition']}"
        for item in context.get("glossary", [])
    ) or "(none)"
    related = "\n\n".join(
        f"[{item['number']} {item['title']}] ({item.get('role', 'section')})\n{item['text']}"
        for item in context.get("linked_sections", context.get("links", []))
    ) or "(none)"
    template = load_template("user")
    return template.format(
        global_context=global_context,
        glossary=glossary,
        related_sections=related,
        section_path=" > ".join(context.get("lineage") or []),
        section_text=context.get("text", ""),
    )


def build_prompt(db: Session, section: Section, instruction: str | None = None) -> tuple[str, dict]:
    context = build_context(db, section)
    prompt = render_prompt(context)
    if instruction:
        prompt = f"{prompt}\n\nHUMAN INSTRUCTION:\n{instruction.strip()}"
    return prompt, context


def snapshot_context(db: Session, section: Section) -> ContextPack:
    prompt, context = build_prompt(db, section)
    pack = ContextPack(
        project_id=section.project_id,
        section_id=section.id,
        prompt=prompt,
        data=context,
    )
    db.add(pack)
    db.commit()
    db.refresh(pack)
    return pack


def context_preview(db: Session, section: Section) -> dict:
    prompt, context = build_prompt(db, section)
    return {
        "section_id": section.id,
        "section": context["section"],
        "context": context,
        "prompt": prompt,
        "links": context["links"],
    }


def truncate_for_trace(text: str, max_tokens: int | None = None) -> str:
    return truncate_text(text, max_tokens or settings.max_leaf_tokens)
