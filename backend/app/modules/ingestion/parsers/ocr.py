from pathlib import Path

from app.modules.ingestion.pivot import PivotDocument


def extract_ocr(path: Path) -> PivotDocument:
    raise NotImplementedError(
        "OCR for scanned PDFs is not implemented yet. "
        "The planned integration is Docling (optional `ocr` extra)."
    )
