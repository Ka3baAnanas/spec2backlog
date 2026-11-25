from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import (
    assistant,
    backlog,
    context,
    document,
    events,
    export,
    pipeline,
    projects,
    questions,
    structure,
    versions,
)
from app.api.v1 import settings as settings_api
from app.core.config import settings
from app.core.db import Base, engine
from app.core.jobs import recover_stale_runs
from app.core.schema import prepare_sqlite_schema
from app.domain import models  # noqa: F401  (register tables)

# Dev-only safety net: if an old local SQLite file predates the current models,
# move it aside and recreate the tables instead of failing at runtime.
prepare_sqlite_schema(settings.database_url)
Base.metadata.create_all(engine)  # TODO: replace by Alembic migrations

@asynccontextmanager
async def lifespan(app: FastAPI):
    recover_stale_runs()
    yield


app = FastAPI(title=settings.app_name, version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (
    projects,
    document,
    structure,
    context,
    pipeline,
    events,
    backlog,
    questions,
    export,
    assistant,
    versions,
    settings_api,
):
    app.include_router(module.router)
