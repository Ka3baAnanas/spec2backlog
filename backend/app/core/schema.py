"""Small, safe schema guard for local SQLite databases.

The project historically shipped without Alembic migrations. During development a
DB file can therefore survive a code change and be missing newly added tables or
columns. For SQLite only, we back up that stale file and let create_all() build a
fresh schema. PostgreSQL deployments are left alone.
"""
import logging
import sqlite3
from pathlib import Path

from sqlalchemy.engine import make_url

logger = logging.getLogger(__name__)

EXPECTED_COLUMNS: dict[str, set[str]] = {
    "nodes": {
        "id", "project_id", "parent_id", "number", "title", "text", "level",
        "position", "is_leaf", "is_global", "is_front_matter", "lineage",
    },
    "run_events": {"id", "project_id", "ts", "stage", "type", "message", "data"},
    "generation_traces": {
        "id", "project_id", "node_id", "prompt", "response_json", "neighbours",
        "global_context_ids", "duration_ms", "attempts", "status", "error",
        "items_created",
    },
}


def sqlite_database_path(database_url: str) -> Path | None:
    """Return the on-disk SQLite path, or None for non-SQLite / in-memory DBs."""
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
