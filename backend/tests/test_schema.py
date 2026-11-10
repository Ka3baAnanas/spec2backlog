import sqlite3

from sqlalchemy import create_engine, inspect

from app import models  # noqa: F401 - register tables on Base.metadata
from app.core.db import Base
from app.core.schema import prepare_sqlite_schema


def _sqlite_url(path):
    return f"sqlite:///{path.as_posix()}"


def test_old_sqlite_schema_is_backed_up_and_recreated(tmp_path):
    db_path = tmp_path / "dev.db"
    connection = sqlite3.connect(db_path)
    connection.execute(
        "CREATE TABLE nodes (id TEXT PRIMARY KEY, project_id TEXT, title TEXT)"
    )
    connection.commit()
    connection.close()

    backup = prepare_sqlite_schema(_sqlite_url(db_path))

    assert backup == tmp_path / "dev.db.bak"
    assert backup.exists()
    assert not db_path.exists()

    engine = create_engine(_sqlite_url(db_path), future=True)
    try:
        Base.metadata.create_all(engine)
        inspector = inspect(engine)
        assert {"run_events", "generation_traces"}.issubset(set(inspector.get_table_names()))
        columns = {column["name"] for column in inspector.get_columns("nodes")}
        assert {"is_front_matter", "is_global", "lineage"}.issubset(columns)
    finally:
        engine.dispose()


def test_current_sqlite_schema_is_kept(tmp_path):
    db_path = tmp_path / "dev.db"
    engine = create_engine(_sqlite_url(db_path), future=True)
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()

    assert prepare_sqlite_schema(_sqlite_url(db_path)) is None
    assert db_path.exists()
