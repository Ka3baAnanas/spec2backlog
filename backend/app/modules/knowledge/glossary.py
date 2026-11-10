"""Glossary / actors extraction. Heuristic now, LLM later."""

import re

from app.domain.enums import SectionRole

_TERM_RE = re.compile(r"^\s*(?:[-*]\s*)?(?P<term>[^:=\-–]{2,80}?)\s*(?::|=|\s[-–]\s)\s*(?P<def>.+)$")
_ACRONYM_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,7}\b")
_ACTOR_HINTS = ("acteur", "actor", "rôle", "role", "utilisateur", "user", "profil")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip(" .;:-–—")


def extract_glossary(sections: list) -> list[dict]:
    terms: dict[str, dict] = {}

    def add(term: str, definition: str, kind: str, section_id: str | None):
        term = _clean(term)
        if len(term) < 2:
            return
        key = term.lower()
        if key not in terms:
            terms[key] = {
                "term": term,
                "definition": _clean(definition)[:1000],
                "kind": kind,
                "source_section_id": section_id,
            }

    for section in sections:
        if section.role != SectionRole.glossary.value:
            continue
        for line in section.text.splitlines():
            match = _TERM_RE.match(line)
            if match:
                term = match.group("term")
                kind = "actor" if any(hint in term.lower() for hint in _ACTOR_HINTS) else "term"
                add(term, match.group("def"), kind, section.id)

    for section in sections:
        for acronym in _ACRONYM_RE.findall(f"{section.title}\n{section.text}"):
            if 2 <= len(acronym) <= 8:
                add(acronym, f"Acronym used in section {section.number or section.title}",
                    "term", section.id)

    return list(terms.values())
