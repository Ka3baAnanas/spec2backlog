from pathlib import Path

from .docx_extractor import extract_docx
from .pdf_extractor import extract_pdf
from .pivot import PivotDocument

# Sections the tutor's template expects; used for the completeness checklist.
EXPECTED_SECTIONS = [
    "contexte", "objectifs", "périmètre", "exigences fonctionnelles",
    "exigences non fonctionnelles", "sécurité", "tests", "outputs",
]


def to_pivot(path: Path) -> PivotDocument:
    ext = path.suffix.lower()
    if ext == ".docx":
        return extract_docx(path)
    if ext == ".pdf":
        return extract_pdf(path)
    raise ValueError(f"Unsupported file type: {ext}")


def checklist(doc: PivotDocument) -> dict:
    titles = " ".join(b.text.lower() for b in doc.blocks if b.kind == "heading")
    found = [s for s in EXPECTED_SECTIONS if s in titles]
    return {"found": found, "missing": [s for s in EXPECTED_SECTIONS if s not in found]}
