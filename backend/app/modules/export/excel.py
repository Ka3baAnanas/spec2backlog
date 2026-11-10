from io import BytesIO

from openpyxl import Workbook


def to_xlsx(rows: list[dict]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Backlog"
    columns = ["key", "kind", "title", "parent", "source", "status", "confidence", "details"]
    sheet.append(columns)
    for row in rows:
        sheet.append([row.get(column, "") for column in columns])
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
