from io import BytesIO

from openpyxl import Workbook


def to_xlsx(rows: list[dict]) -> bytes:
    wb = Workbook(); ws = wb.active; ws.title = "Backlog"
    cols = ["kind", "title", "parent", "source", "status", "details"]
    ws.append(cols)
    for r in rows:
        ws.append([r.get(c, "") for c in cols])
    buf = BytesIO(); wb.save(buf)
    return buf.getvalue()
