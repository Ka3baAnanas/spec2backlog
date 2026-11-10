from pathlib import Path

from .pivot import Block, PivotDocument


def extract_pdf(path: Path) -> PivotDocument:
    """Text PDFs via pdfplumber. Headings are detected by font size (largest sizes => headings).
    TODO: scanned PDFs -> OCR (docling) only when a page has no text layer."""
    import pdfplumber

    out = PivotDocument(source=path.name)
    with pdfplumber.open(str(path)) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            lines = page.extract_text_lines() or []
            if not lines:
                out.warnings.append(f"page {i}: no text layer (scanned?) -> OCR needed")
                continue
            for ln in lines:
                size = max((c.get("size", 0) for c in ln["chars"]), default=0)
                text = ln["text"].strip()
                if not text:
                    continue
                if size >= 14 and len(text) < 120:
                    out.blocks.append(Block("heading", text, 1 if size >= 18 else 2))
                else:
                    out.blocks.append(Block("paragraph", text))
    return out
