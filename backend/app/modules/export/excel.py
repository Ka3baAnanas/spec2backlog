"""Excel export: one workbook with backlog, traceability and validation sheets."""

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return "; ".join(str(item) for item in value if str(item).strip())
    if isinstance(value, dict):
        return "; ".join(f"{key}: {item}" for key, item in value.items())
    return str(value)


def _add_sheet(workbook: Workbook, title: str, headers: list[str], rows: list[list], widths=None):
    sheet = workbook.create_sheet(title)
    sheet.append(headers)
    for row in rows:
        sheet.append([_text(cell) for cell in row])

    header_fill = PatternFill("solid", fgColor="FFE600")
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="1A1A24")
        cell.fill = header_fill
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = (
        sheet.dimensions
        if sheet.max_row > 1
        else f"A1:{get_column_letter(len(headers))}1"
    )
    sheet.row_dimensions[1].height = 24

    default_widths = widths or [22, 36, 60, 28, 18, 16]
    for index, width in enumerate(default_widths, 1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    return sheet


def _story_body(story: dict) -> dict:
    return story.get("body") or {}


def _persona(story: dict) -> str:
    body = _story_body(story)
    return body.get("persona") or body.get("as_a") or ""


def _goal(story: dict) -> str:
    body = _story_body(story)
    return body.get("goal") or body.get("i_want") or ""


def _benefit(story: dict) -> str:
    body = _story_body(story)
    return body.get("benefit") or body.get("so_that") or ""


def to_xlsx(payload: dict) -> bytes:
    workbook = Workbook()
    workbook.remove(workbook.active)

    epic_rows = []
    feature_rows = []
    story_rows = []
    criteria_rows = []
    test_rows = []
    trace_rows = []

    for epic in payload["epics"]:
        epic_item = epic["item"]
        epic_rows.append(
            [
                epic_item.key,
                epic["title"],
                epic["summary"],
                epic_item.status,
                _text(epic_item.source_sections),
            ]
        )
        for feature in epic["features"]:
            feature_item = feature["item"]
            feature_rows.append(
                [
                    feature_item.key if feature_item else "",
                    epic_item.key,
                    epic["title"],
                    feature["title"],
                    feature["summary"],
                    feature_item.status if feature_item else "approved",
                ]
            )
            for story in feature["stories"]:
                story_item = story["item"]
                body = story["body"]
                story_rows.append(
                    [
                        story_item.key,
                        feature_item.key if feature_item else "",
                        epic_item.key,
                        story["title"],
                        _persona(story),
                        _goal(story),
                        _benefit(story),
                        body.get("description", ""),
                        body.get("priority", ""),
                        body.get("priority_reason", ""),
                        body.get("estimate", ""),
                        _text(body.get("dependencies")),
                        story_item.status,
                        round(story["confidence"], 2),
                    ]
                )
                for criterion in body.get("acceptance_criteria") or []:
                    criteria_rows.append(
                        [story_item.key, story["title"], _text(criterion)]
                    )
                test_keys = []
                for test in story["tests"]:
                    test_body = test.body or {}
                    test_keys.append(test.key)
                    test_rows.append(
                        [
                            test.key,
                            story_item.key,
                            story["title"],
                            test.title,
                            _text(test_body.get("preconditions")),
                            _text(test_body.get("steps")),
                            _text(test_body.get("test_data")),
                            _text(test_body.get("expected")),
                            test.status,
                        ]
                    )
                for section in story["source_sections"]:
                    trace_rows.append(
                        [
                            f"{section['number']} {section['title']}".strip(),
                            story_item.key,
                            story["title"],
                            ", ".join(test_keys) or "No test",
                        ]
                    )

    question_rows = [
        [
            question["priority"],
            question["text"],
            f"{question['source']['number']} {question['source']['title']}".strip(),
            question["status"],
            question["answer"],
        ]
        for question in payload["questions"]
    ]

    validation_rows = []
    for entry in payload["validation"]:
        item = entry["item"]
        parent = entry["parent"]
        validation_rows.append(
            [
                item.key,
                item.kind,
                item.title,
                parent.key if parent else "",
                entry["before_status"],
                entry["after_status"],
                entry["action"],
                entry["by"],
                entry["at"].isoformat(sep=" ") if entry["at"] else "",
            ]
        )

    _add_sheet(
        workbook,
        "Epics",
        ["Key", "Title", "Summary", "Status", "Source sections"],
        epic_rows,
        [10, 34, 70, 14, 30],
    )
    _add_sheet(
        workbook,
        "Features",
        ["Key", "Epic", "Epic title", "Feature", "Summary", "Status"],
        feature_rows,
        [10, 10, 34, 30, 55, 14],
    )
    _add_sheet(
        workbook,
        "Stories",
        [
            "Key", "Feature", "Epic", "Title", "Persona", "Goal", "Benefit", "Description",
            "Priority", "Priority reason", "Estimate", "Dependencies", "Status", "Confidence",
        ],
        story_rows,
        [10, 10, 10, 38, 20, 42, 42, 60, 12, 40, 10, 30, 12, 12],
    )
    _add_sheet(
        workbook,
        "Acceptance criteria",
        ["Story", "Story title", "Criterion"],
        criteria_rows,
        [10, 38, 85],
    )
    _add_sheet(
        workbook,
        "Test cases",
        ["Key", "Story", "Story title", "Title", "Preconditions", "Steps", "Test data", "Expected", "Status"],
        test_rows,
        [10, 10, 34, 32, 36, 46, 34, 46, 12],
    )
    _add_sheet(
        workbook,
        "Traceability matrix",
        ["Source section", "Story", "Story title", "Tests"],
        trace_rows,
        [34, 10, 40, 22],
    )
    _add_sheet(
        workbook,
        "Open questions",
        ["Priority", "Question", "Source section", "Status", "Answer"],
        question_rows,
        [14, 85, 34, 14, 45],
    )
    _add_sheet(
        workbook,
        "Validation report",
        ["Item", "Kind", "Title", "Parent", "Before", "After", "Action", "Who", "When"],
        validation_rows,
        [10, 12, 40, 10, 14, 14, 16, 18, 22],
    )

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
