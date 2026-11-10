"""Ingestion quality: completeness checklist, warnings and stats."""

from app.modules.ingestion.pivot import PivotDocument

EXPECTED_SECTIONS = [
    "contexte",
    "objectifs",
    "périmètre",
    "exigences fonctionnelles",
    "exigences non fonctionnelles",
    "sécurité",
    "tests",
    "outputs",
]


def checklist(doc: PivotDocument) -> dict:
    titles = " ".join(block.text.lower() for block in doc.blocks if block.kind == "heading")
    found = [section for section in EXPECTED_SECTIONS if section in titles]
    return {
        "found": found,
        "missing": [section for section in EXPECTED_SECTIONS if section not in found],
    }


def warnings(doc: PivotDocument) -> list[str]:
    out = list(doc.warnings)
    if not any(block.kind == "heading" for block in doc.blocks):
        out.append("No heading detected: the whole document will be treated as one section.")
    if doc.skipped_toc:
        out.append(f"Skipped {doc.skipped_toc} table-of-contents line(s).")
    if not any(block.kind in ("paragraph", "list", "table") for block in doc.blocks):
        out.append("No body text detected in the document.")
    return out


def stats(doc: PivotDocument) -> dict:
    return {
        "blocks": len(doc.blocks),
        "paragraphs": sum(1 for block in doc.blocks if block.kind == "paragraph"),
        "tables": sum(1 for block in doc.blocks if block.kind == "table"),
        "headings": sum(1 for block in doc.blocks if block.kind == "heading"),
        "list_items": sum(1 for block in doc.blocks if block.kind == "list"),
        "skipped_toc": doc.skipped_toc,
        "warnings": len(doc.warnings),
        "characters": sum(len(block.text) for block in doc.blocks),
    }


def pivot_preview(doc: PivotDocument, limit: int = 60) -> list[dict]:
    return [
        {"kind": block.kind, "text": block.text[:500], "level": block.level}
        for block in doc.blocks[:limit]
    ]
