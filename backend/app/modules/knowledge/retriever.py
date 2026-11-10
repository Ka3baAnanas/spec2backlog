"""Hybrid retrieval: vector similarity + explicit references + lexical overlap."""

import logging
import re
from collections import Counter

from app.core.config import settings
from app.core.events import emit
from app.domain.enums import LinkKind
from app.modules.knowledge.embedder import embed_texts
from app.modules.knowledge.vector_store import get_store

logger = logging.getLogger(__name__)

REF_RE = re.compile(
    r"(?:voir|cf\.?|section|§)\s*(?:§\s*)?(\d+(?:\.\d+)*)", re.IGNORECASE
)
_WORD_RE = re.compile(r"[a-zA-ZÀ-ÖØ-öø-ÿ]{3,}")
STOPWORDS = {
    "les", "des", "une", "aux", "pour", "dans", "avec", "sur", "est", "sont", "que", "qui",
    "the", "and", "for", "with", "this", "that", "from", "into", "shall", "must", "can",
    "être", "etre", "par", "pas", "plus", "tout", "tous", "elle", "ils", "nous", "vous",
}


def explicit_refs(text: str) -> set[str]:
    return set(REF_RE.findall(text or ""))


def keywords(text: str) -> set[str]:
    return {word.lower() for word in _WORD_RE.findall(text or "") if word.lower() not in STOPWORDS}


def lexical_score(left: str, right: str) -> tuple[float, list[str]]:
    left_words, right_words = keywords(left), keywords(right)
    if not left_words or not right_words:
        return 0.0, []
    shared = sorted(left_words & right_words)
    score = len(shared) / min(len(left_words), len(right_words))
    return score, shared[:8]


def _candidates(sections):
    return [
        section for section in sections
        if section.text.strip() and section.role not in ("front_matter", "ignored")
    ]


def retrieve_links(project_id: str, sections: list, *, emit_events: bool = True) -> list[dict]:
    candidates = _candidates(sections)
    total = len(candidates)
    if emit_events:
        emit(project_id, "knowledge", "stage_start",
             f"Linking {total} section(s) with hybrid retrieval", {"sections": total})

    def on_event(kind: str, message: str, data: dict) -> None:
        if emit_events:
            emit(project_id, "knowledge", kind, message, data)

    vectors = embed_texts(
        [f"{section.title}\n{section.text}" for section in candidates], on_event=on_event
    )
    store = get_store()
    store.upsert(project_id, [section.id for section in candidates], vectors)

    by_number = {section.number: section for section in candidates if section.number}
    found: dict[tuple[str, str], dict] = {}

    def add(source, target, kind, score, reason):
        if source.id == target.id:
            return
        key = (source.id, target.id)
        current = found.get(key)
        if current is None or score > current["score"]:
            found[key] = {
                "source_id": source.id,
                "target_id": target.id,
                "kind": kind,
                "score": float(score),
                "reason": reason,
                "enabled": True,
            }

    for index, (section, vector) in enumerate(zip(candidates, vectors), 1):
        if emit_events:
            emit(project_id, "knowledge", "progress",
                 f"Linked {index}/{total}: {section.number or section.title}",
                 {"i": index, "N": total, "section_id": section.id,
                  "number": section.number, "title": section.title})

        for target_id, score in store.neighbours(
            project_id, vector, settings.similar_top_k, exclude=section.id
        ):
            if score >= settings.similar_min_score:
                target = next(item for item in candidates if item.id == target_id)
                add(section, target, LinkKind.similarity.value, score,
                    f"vector similarity {score:.2f}")

        for number in explicit_refs(section.text):
            target = by_number.get(number)
            if target:
                add(section, target, LinkKind.reference.value, 1.0,
                    f"explicit reference to section {number}")

        for target in candidates:
            if target.id == section.id:
                continue
            score, shared = lexical_score(section.text, target.text)
            if score >= settings.lexical_min_score:
                add(section, target, LinkKind.lexical.value, score,
                    "shared keywords: " + ", ".join(shared))

    links = list(found.values())
    by_kind = dict(Counter(link["kind"] for link in links))
    linked_ids = {link["source_id"] for link in links} | {link["target_id"] for link in links}
    if emit_events:
        emit(project_id, "knowledge", "stage_end",
             f"Knowledge links built: {len(links)}",
             {"sections": total, "links": len(links), "links_by_kind": by_kind,
              "sections_without_links": [s.id for s in candidates if s.id not in linked_ids]})
    return links


def retrieve_citations(project_id: str, question: str, sections: list, top_k: int = 5) -> list[dict]:
    """Return scored sections + snippet for the assistant, with a human-readable reason."""
    candidates = _candidates(sections)
    if not candidates:
        return []

    scores: dict[str, dict] = {}
    for section in candidates:
        score, shared = lexical_score(question, f"{section.title} {section.text}")
        if score > 0:
            scores[section.id] = {
                "section": section, "score": score,
                "reason": "keyword overlap: " + ", ".join(shared),
            }

    try:
        vector = embed_texts([question], task="query")[0]
        store = get_store()
        store.upsert(
            project_id,
            [section.id for section in candidates],
            embed_texts([f"{section.title}\n{section.text}" for section in candidates]),
        )
        by_id = {section.id: section for section in candidates}
        for section_id, similarity in store.neighbours(project_id, vector, top_k):
            section = by_id.get(section_id)
            if section is None:
                continue
            entry = scores.setdefault(
                section_id,
                {"section": section, "score": 0.0, "reason": ""},
            )
            if similarity > entry["score"]:
                entry["score"] = float(similarity)
                entry["reason"] = f"vector similarity {similarity:.2f}"
    except Exception:  # pragma: no cover - retrieval should degrade, not fail
        logger.exception("vector retrieval failed for project %s; lexical only", project_id)

    ordered = sorted(scores.values(), key=lambda entry: -entry["score"])
    out = []
    for entry in ordered[:top_k]:
        section = entry["section"]
        snippet = section.text.strip().replace("\n", " ")[:320]
        out.append({
            "section_id": section.id,
            "number": section.number,
            "title": section.title,
            "score": round(entry["score"], 4),
            "reason": entry["reason"],
            "snippet": snippet,
            "text": section.text,
        })
    return out

