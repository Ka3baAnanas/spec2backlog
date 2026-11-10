"""Small, safe schema guard for local SQLite databases.

The project does not ship migrations yet. During development a DB file can survive
a code change and be missing newly added tables or columns. For SQLite only we back
up that stale file and let create_all() build a fresh schema. PostgreSQL is left alone.
"""
import logging
import sqlite3
from pathlib import Path

from sqlalchemy.engine import make_url

logger = logging.getLogger(__name__)

EXPECTED_COLUMNS: dict[str, set[str]] = {
    "projects": {
        "id", "name", "status", "error", "checklist", "context_approved",
        "created_at", "updated_at",
    },
    "documents": {"id", "project_id", "version", "filename", "path", "stats", "warnings",
                  "checklist", "created_at"},
    "sections": {
        "id", "project_id", "document_id", "parent_id", "number", "title", "text", "level",
        "position", "is_leaf", "role", "lineage",
    },
    "links": {"id", "project_id", "source_id", "target_id", "kind", "score", "reason", "enabled"},
    "glossary_terms": {"id", "project_id", "term", "definition", "kind", "source_section_id"},
    "context_packs": {"id", "project_id", "section_id", "prompt", "data", "created_at"},
    "backlog_items": {
        "id", "project_id", "key", "kind", "parent_item_id", "source_section_id",
        "source_sections", "title", "body", "status", "confidence", "questions",
    },
    "questions": {"id", "project_id", "section_id", "text", "answer", "status", "created_at"},
    "generation_traces": {
        "id", "project_id", "section_id", "prompt", "response_json", "links",
        "global_context_ids", "duration_ms", "attempts", "status", "error", "items_created",
    },
    "run_events": {"id", "project_id", "ts", "stage", "type", "message", "data"},
    "review_events": {"id", "project_id", "item_id", "action", "before", "after", "by", "at"},
}


def sqlite_database_path(database_url: str) -> Path | None:
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite":
        return None
    database = url.database
    if not database or database == ":memory:":
        return None
    return Path(database)


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    rows = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
    return {row[1] for row in rows}


def sqlite_schema_is_outdated(path: Path) -> bool:
    connection = sqlite3.connect(str(path))
    try:
        for table, expected in EXPECTED_COLUMNS.items():
            existing = _table_columns(connection, table)
            if existing and not expected.issubset(existing):
                missing = sorted(expected - existing)
                logger.warning("SQLite table %s is missing columns: %s", table, ", ".join(missing))
                return True
        return False
    finally:
        connection.close()


def prepare_sqlite_schema(database_url: str) -> Path | None:
    """Back up a stale local SQLite DB so create_all() can recreate the schema.

    Returns the backup path when the file was replaced, otherwise None.
    """
    path = sqlite_database_path(database_url)
    if path is None or not path.exists():
        return None
    if not sqlite_schema_is_outdated(path):
        return None

    backup = path.with_name(path.name + ".bak")
    if backup.exists():
        backup.unlink()
    path.replace(backup)
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(path) + suffix)
        if sidecar.exists():
            sidecar.unlink()

    logger.warning("Old SQLite schema moved to %s; a fresh dev database will be created", backup)
    return backup
