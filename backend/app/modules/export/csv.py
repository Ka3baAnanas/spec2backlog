import csv
from io import StringIO


def to_csv(rows: list[dict]) -> bytes:
    columns = ["key", "kind", "title", "parent", "source", "status", "confidence", "details"]
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column, "") for column in columns})
    return buffer.getvalue().encode("utf-8-sig")
