import re
from pathlib import Path

import docx
from docx.table import Table
from docx.text.paragraph import Paragraph

from .pivot import Block, PivotDocument

NUM_RE = re.compile(r"^(\d+(?:\.\d+)*)[.)]?\s+\S")


def _heading_level(p: Paragraph) -> int:
    name = p.style.name or ""
    if name.lower().startswith("heading"):
        digits = re.findall(r"\d+", name)
        lvl = int(digits[0]) if digits else 1
    elif name == "Title":
        return 0
    else:
        lvl = 0
    # Fallback/refinement: numbering "4.1.2" is the truth about depth
    m = NUM_RE.match(p.text.strip())
    if m and (lvl or name.lower().startswith("heading")):
        lvl = m.group(1).count(".") + 1
    return lvl


def _iter_body(document):
    for child in document.element.body.iterchildren():
        if child.tag.endswith("}p"):
            yield Paragraph(child, document)
        elif child.tag.endswith("}tbl"):
            yield Table(child, document)


def extract_docx(path: Path) -> PivotDocument:
    d = docx.Document(str(path))
    out = PivotDocument(source=path.name)
    for item in _iter_body(d):
        if isinstance(item, Table):
            rows = [" | ".join(c.text.strip() for c in r.cells) for r in item.rows]
            if any(rows):
                out.blocks.append(Block("table", "\n".join(rows)))
            continue
        text = item.text.strip()
        if not text:
            continue
        style = item.style.name or ""
        if style.lower().startswith("toc"):
            out.skipped_toc += 1  # table of contents is noise
            continue
        lvl = _heading_level(item)
        if lvl:
            out.blocks.append(Block("heading", text, lvl))
        elif "list" in style.lower():
            out.blocks.append(Block("list", "- " + text))
        else:
            out.blocks.append(Block("paragraph", text))
    return out
