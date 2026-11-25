"""Word export: a complete backlog document with traceability and validation report."""

from io import BytesIO

from docx import Document as DocxDocument
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return "; ".join(str(item) for item in value if str(item).strip())
    if isinstance(value, dict):
        return "; ".join(f"{key}: {item}" for key, item in value.items())
    return str(value)


def _paragraph(doc, text: str, bold: bool = False, size: int | None = None):
    paragraph = doc.add_paragraph()
    run = paragraph.add_run(text)
    run.bold = bold
    if size:
        run.font.size = Pt(size)
    return paragraph


def _bullets(doc, values: list, label: str | None = None):
    if label:
        _paragraph(doc, label, bold=True)
    for value in values:
        text = _text(value)
        if text:
            doc.add_paragraph(text, style="List Bullet")


def _table(doc, headers: list[str], rows: list[list]):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Light Grid Accent 1"
    for index, header in enumerate(headers):
        cell = table.rows[0].cells[index]
        cell.text = header
        for paragraph in cell.paragraphs:
            for run in paragraph.runs:
                run.bold = True
    for row in rows:
        cells = table.add_row().cells
        for index, value in enumerate(row):
            cells[index].text = _text(value)
    doc.add_paragraph()
    return table


def _cover(doc, project, payload: dict):
    for _ in range(4):
        doc.add_paragraph()
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("Backlog document")
    run.bold = True
    run.font.size = Pt(30)
    run.font.color.rgb = RGBColor(0x2E, 0x2E, 0x38)

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subtitle.add_run(project.name)
    run.font.size = Pt(18)
    run.font.color.rgb = RGBColor(0x2E, 0x2E, 0x38)

    metadata = doc.add_paragraph()
    metadata.alignment = WD_ALIGN_PARAGRAPH.CENTER
    metadata.add_run(
        f"Version {payload.get('version', 1)}  |  {project.created_at.strftime('%d %B %Y') if project.created_at else ''}"
    )
    doc.add_page_break()


def _summary(doc, payload: dict):
    doc.add_heading("Summary", level=1)
    stories = payload["stories"]
    tests = [test for story in stories for test in story["tests"]]
    approved = sum(1 for story in stories if story["status"] == "approved")
    edited = sum(1 for story in stories if story["status"] == "edited")
    _paragraph(
        doc,
        (
            f"This backlog contains {len(payload['epics'])} epics, "
            f"{payload['feature_count']} features, {len(stories)} approved stories and "
            f"{len(tests)} test cases. Traceability coverage is {payload['coverage']}% across "
            f"{payload['requirement_sections']} requirement sections. "
            f"{approved} stories were approved as proposed and {edited} were approved after editing. "
            f"{len(payload['questions'])} open questions remain for the client."
        ),
    )
    doc.add_paragraph()


def _backlog(doc, payload: dict):
    for epic in payload["epics"]:
        epic_item = epic["item"]
        doc.add_heading(f"{epic_item.key}  {epic['title']}", level=1)
        if epic["summary"]:
            _paragraph(doc, epic["summary"])
        for feature in epic["features"]:
            feature_item = feature["item"]
            key = f"{feature_item.key}  " if feature_item else ""
            doc.add_heading(f"{key}{feature['title']}", level=2)
            if feature["summary"]:
                _paragraph(doc, feature["summary"])
            for story in feature["stories"]:
                item = story["item"]
                body = story["body"]
                doc.add_heading(f"{item.key}  {story['title']}", level=3)
                persona = body.get("persona") or body.get("as_a") or ""
                goal = body.get("goal") or body.get("i_want") or ""
                benefit = body.get("benefit") or body.get("so_that") or ""
                _paragraph(
                    doc,
                    f"As a {persona}, I want {goal}, so that {benefit}.",
                )
                if body.get("description"):
                    _paragraph(doc, body["description"])
                _bullets(doc, body.get("business_rules") or [], "Business rules")
                _paragraph(
                    doc,
                    (
                        f"Priority: {body.get('priority', '')} "
                        f"({body.get('priority_reason', '')}). "
                        f"Estimate: {body.get('estimate', '')}. "
                        f"Dependencies: {_text(body.get('dependencies')) or 'None'}."
                    ),
                )
                _bullets(
                    doc,
                    body.get("acceptance_criteria") or [],
                    "Acceptance criteria",
                )
                if story["tests"]:
                    _paragraph(doc, "Tests", bold=True)
                    for test in story["tests"]:
                        test_body = test.body or {}
                        doc.add_heading(f"{test.key}  {test.title}", level=4)
                        _bullets(doc, test_body.get("preconditions") or [], "Preconditions")
                        _bullets(doc, test_body.get("steps") or [], "Steps")
                        _paragraph(doc, f"Test data: {_text(test_body.get('test_data')) or 'None'}")
                        _paragraph(doc, f"Expected: {_text(test_body.get('expected'))}")
        doc.add_paragraph()


def _traceability(doc, payload: dict):
    doc.add_page_break()
    doc.add_heading("Traceability matrix", level=1)
    rows = []
    for story in payload["stories"]:
        item = story["item"]
        for section in story["source_sections"]:
            rows.append(
                [
                    f"{section['number']} {section['title']}".strip(),
                    item.key,
                    story["title"],
                    ", ".join(test.key for test in story["tests"]) or "No test",
                ]
            )
    _table(doc, ["Source section", "Story", "Story title", "Tests"], rows)


def _questions(doc, payload: dict):
    doc.add_page_break()
    doc.add_heading("Open questions", level=1)
    rows = [
        [
            question["priority"],
            question["text"],
            f"{question['source']['number']} {question['source']['title']}".strip(),
            question["status"],
        ]
        for question in payload["questions"]
    ]
    if rows:
        _table(doc, ["Priority", "Question", "Source section", "Status"], rows)
    else:
        _paragraph(doc, "No open questions remain.")


def _validation(doc, payload: dict):
    doc.add_page_break()
    doc.add_heading("Validation report", level=1)
    rows = []
    for entry in payload["validation"]:
        item = entry["item"]
        rows.append(
            [
                item.key,
                item.kind,
                item.title,
                entry["before_status"],
                entry["after_status"],
                entry["action"],
                entry["by"],
                entry["at"].strftime("%d %b %Y %H:%M") if entry["at"] else "",
            ]
        )
    if rows:
        _table(
            doc,
            ["Item", "Kind", "Title", "Before", "After", "Action", "Who", "When"],
            rows,
        )
    else:
        _paragraph(doc, "No validation decisions recorded yet.")


def to_docx(payload: dict) -> bytes:
    project = payload["project"]
    doc = DocxDocument()
    styles = doc.styles
    for style_name in ("Normal",):
        style = styles[style_name]
        style.font.name = "Calibri"
        style.font.size = Pt(10.5)
    _cover(doc, project, payload)
    _summary(doc, payload)
    _backlog(doc, payload)
    _traceability(doc, payload)
    _questions(doc, payload)
    _validation(doc, payload)

    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
