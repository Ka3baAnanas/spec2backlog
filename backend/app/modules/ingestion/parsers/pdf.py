from pathlib import Path

from app.modules.ingestion.pivot import Block, PivotDocument


def extract_pdf(path: Path) -> PivotDocument:
    """Text PDFs via pdfplumber. Headings are detected by font size."""
    import pdfplumber

    out = PivotDocument(source=path.name)
    with pdfplumber.open(str(path)) as pdf:
        for index, page in enumerate(pdf.pages, 1):
            lines = page.extract_text_lines() or []
            if not lines:
                out.warnings.append(f"page {index}: no text layer (scanned?) -> OCR needed")
                continue
            for line in lines:
                size = max((char.get("size", 0) for char in line["chars"]), default=0)
                text = line["text"].strip()
                if not text:
                    continue
                if size >= 14 and len(text) < 120:
                    out.blocks.append(Block("heading", text, 1 if size >= 18 else 2))
                else:
                    out.blocks.append(Block("paragraph", text))
    return out
