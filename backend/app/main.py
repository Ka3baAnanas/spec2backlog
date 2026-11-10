from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect

from app import models  # noqa: F401  (register tables)
from app.api.routes import router
from app.core.config import settings
from app.core.db import Base, engine
from app.core.schema import prepare_sqlite_schema

# Dev-only safety net: if an old local SQLite file predates the current models,
# move it aside and recreate the tables instead of failing at runtime.
prepare_sqlite_schema(settings.database_url)
Base.metadata.create_all(engine)  # TODO: replace by Alembic migrations


def _add_missing_columns():
    """Non-SQLite additive fallback until real Alembic migrations are in place."""
    if settings.database_url.startswith("sqlite"):
        return
    inspector = inspect(engine)
    if "nodes" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("nodes")}
    if "is_front_matter" not in columns:
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "ALTER TABLE nodes ADD COLUMN is_front_matter BOOLEAN NOT NULL DEFAULT FALSE"
            )


_add_missing_columns()

app = FastAPI(title="Spec2Backlog", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])
app.include_router(router)
