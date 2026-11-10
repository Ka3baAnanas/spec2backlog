import asyncio
import json
import tempfile
import time
import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal, get_db
from app.models import (
    BacklogItem,
    Edge,
    GenerationTrace,
    ItemStatus,
    Node,
    Project,
    ValidationEvent,
)
from app.schemas import ItemOut, ItemPatch, NodeOut, ProjectOut
from app.services.events import emit, fetch_events
from app.services.export.excel import to_xlsx
from app.services.generation.runner import generate_project
from app.services.graph.builder import build_graph_for_project
from app.services.ingestion import checklist, to_pivot
from app.services.pipeline import ALLOWED_STAGES, start_pipeline
from app.services.tree.builder import build_tree

router = APIRouter(prefix="/api/v1")


def _project(db: Session, pid: str) -> Project:
    p = db.get(Project, pid)
    if not p:
        raise HTTPException(404, "project not found")
    return p


@router.get("/health")
def health():
    return {"ok": True}


def _emit_ingestion_events(project_id: str, pivot) -> None:
    counts = {
        "paragraphs": sum(1 for b in pivot.blocks if b.kind == "paragraph"),
        "tables": sum(1 for b in pivot.blocks if b.kind == "table"),
        "headings": sum(1 for b in pivot.blocks if b.kind == "heading"),
        "list_items": sum(1 for b in pivot.blocks if b.kind == "list"),
        "skipped_toc": pivot.skipped_toc,
        "warnings": len(pivot.warnings),
    }
    emit(project_id, "ingestion", "stage_start", "Ingestion started", counts)
    emit(
        project_id,
        "ingestion",
        "progress",
        (f"Extracted {counts['headings']} headings, {counts['paragraphs']} paragraphs, "
         f"{counts['tables']} tables, {counts['list_items']} list items"),
        counts,
    )
    for warning in pivot.warnings:
        emit(project_id, "ingestion", "warning", warning, {"warning": warning})
    emit(project_id, "ingestion", "stage_end", "Ingestion finished", counts)


def _emit_tree_events(project_id: str, tree) -> None:
    nodes = list(tree.values())
    data = {
        "nodes": len(nodes),
        "leaves": sum(1 for n in nodes if n.is_leaf and n.text.strip()),
        "max_depth": max((n.level for n in nodes), default=0),
        "front_matter_skipped": sum(1 for n in nodes if n.is_front_matter),
        "global_context_nodes": [
            {"node_id": n.id, "title": n.title} for n in nodes if n.is_global
        ],
    }
    emit(project_id, "tree", "stage_start", "Building document tree", data)
    emit(
        project_id,
        "tree",
        "progress",
        (f"Tree built: {data['nodes']} nodes, {data['leaves']} leaves, "
         f"depth {data['max_depth']}, {data['front_matter_skipped']} front-matter skipped"),
        data,
    )
    emit(project_id, "tree", "stage_end", "Tree ready", data)


# 1) Ingestion + tree ---------------------------------------------------------
@router.post("/projects/upload", response_model=ProjectOut)
async def upload(name: str = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db)):
    suffix = Path(file.filename or "").suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
    try:
        pivot = to_pivot(Path(tmp.name))
    except ValueError as e:
        raise HTTPException(415, str(e))
    pivot.source = file.filename or pivot.source
    project = Project(name=name, status="ingested", checklist=checklist(pivot))
    db.add(project); db.flush()
    tree = build_tree(pivot, lambda: uuid.uuid4().hex)
    for pos, n in enumerate(tree.values()):
        db.add(Node(id=n.id, project_id=project.id, parent_id=n.parent, number=n.number, title=n.title,
                    text=n.text, level=n.level, position=pos, is_leaf=n.is_leaf and bool(n.text.strip()),
                    is_global=n.is_global, is_front_matter=n.is_front_matter, lineage=n.lineage))
    db.commit()
    _emit_ingestion_events(project.id, pivot)
    _emit_tree_events(project.id, tree)
    return project


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    return db.scalars(select(Project)).all()


@router.get("/projects/{pid}/tree", response_model=list[NodeOut])
def get_tree(pid: str, db: Session = Depends(get_db)):
    _project(db, pid)
    return db.scalars(select(Node).where(Node.project_id == pid).order_by(Node.position)).all()


# 2) Meaning graph ------------------------------------------------------------
@router.post("/projects/{pid}/graph")
def build_graph(pid: str, db: Session = Depends(get_db)):
    return build_graph_for_project(db, _project(db, pid))


@router.get("/projects/{pid}/graph")
def get_graph(pid: str, db: Session = Depends(get_db)):
    return [{"source": e.source_id, "target": e.target_id, "kind": e.kind, "score": e.score}
            for e in db.scalars(select(Edge).where(Edge.project_id == pid))]


# 3) Generation ---------------------------------------------------------------
@router.post("/projects/{pid}/generate")
def generate(pid: str, only_failed: bool = Query(False), db: Session = Depends(get_db)):
    return {"items": generate_project(db, _project(db, pid), only_failed=only_failed)}


@router.post("/projects/{pid}/run")
def run_pipeline(
    pid: str,
    stages: str = Query("graph,generate"),
    db: Session = Depends(get_db),
):
    """Start graph/generation in a background thread and return immediately."""
    _project(db, pid)
    requested = [stage.strip() for stage in stages.split(",") if stage.strip()]
    if not requested:
        requested = list(ALLOWED_STAGES)
    unknown = [stage for stage in requested if stage not in ALLOWED_STAGES]
    if unknown:
        raise HTTPException(400, f"unknown stage(s): {', '.join(unknown)}")
    return start_pipeline(pid, requested)


@router.get("/projects/{pid}/items", response_model=list[ItemOut])
def items(pid: str, status: str | None = None, db: Session = Depends(get_db)):
    q = select(BacklogItem).where(BacklogItem.project_id == pid)
    if status:
        q = q.where(BacklogItem.status == ItemStatus(status))
    return db.scalars(q).all()


@router.get("/projects/{pid}/leaves/{node_id}/trace")
def leaf_trace(pid: str, node_id: str, db: Session = Depends(get_db)):
    _project(db, pid)
    traces = db.scalars(
        select(GenerationTrace)
        .where(GenerationTrace.project_id == pid, GenerationTrace.node_id == node_id)
        .order_by(GenerationTrace.id.desc())
        .limit(1)
    ).all()
    if not traces:
        raise HTTPException(404, "no generation trace for this leaf")
    t = traces[0]
    return {
        "id": t.id,
        "project_id": t.project_id,
        "node_id": t.node_id,
        "prompt": t.prompt,
        "response_json": t.response_json,
        "neighbours": t.neighbours or [],
        "global_context_ids": t.global_context_ids or [],
        "duration_ms": t.duration_ms,
        "attempts": t.attempts,
        "status": t.status,
        "error": t.error,
        "items_created": t.items_created or {},
    }


# 4) Observability: replay + live SSE ----------------------------------------
@router.get("/projects/{pid}/events.json")
def events_json(
    pid: str,
    after: int = 0,
    limit: int = Query(1000, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    _project(db, pid)
    return fetch_events(pid, after=after, limit=limit)


@router.get("/projects/{pid}/events")
async def stream_events(
    pid: str,
    request: Request,
    last_event_id: str | None = None,
):
    def _exists() -> bool:
        with SessionLocal() as session:
            return session.get(Project, pid) is not None

    if not await run_in_threadpool(_exists):
        raise HTTPException(404, "project not found")

    header_id = request.headers.get("last-event-id")
    try:
        after = int(header_id or last_event_id or 0)
    except (TypeError, ValueError):
        after = 0

    async def generator():
        nonlocal after
        last_heartbeat = time.monotonic()
        while True:
            if await request.is_disconnected():
                break
            events = await run_in_threadpool(fetch_events, pid, after, 500)
            for event in events:
                after = event["id"]
                payload = json.dumps(event, ensure_ascii=False)
                yield (
                    f"id: {event['id']}\n"
                    f"event: {event['type']}\n"
                    f"data: {payload}\n\n"
                )
            now = time.monotonic()
            if now - last_heartbeat >= 15:
                last_heartbeat = now
                yield ": heartbeat\n\n"
            await asyncio.sleep(0.5 if events else 1.0)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive",
                 "X-Accel-Buffering": "no"},
    )


# 5) Human validation ---------------------------------------------------------
@router.patch("/items/{iid}", response_model=ItemOut)
def validate_item(iid: str, patch: ItemPatch, db: Session = Depends(get_db)):
    it = db.get(BacklogItem, iid)
    if not it:
        raise HTTPException(404)
    before = {"title": it.title, "body": it.body, "status": it.status.value}
    if patch.title is not None:
        it.title = patch.title
    if patch.body is not None:
        it.body = patch.body
    it.status = ItemStatus(patch.status) if patch.status else (
        ItemStatus.edited if (patch.title or patch.body) else it.status)
    db.add(ValidationEvent(item_id=iid, action=it.status.value, before=before,
                           after={"title": it.title, "body": it.body}, by=patch.by))
    db.commit()
    return it


# 6) Export -------------------------------------------------------------------
@router.get("/projects/{pid}/export.xlsx")
def export_xlsx(pid: str, db: Session = Depends(get_db)):
    emit(pid, "export", "stage_start", "Preparing Excel export", {})
    nodes = {n.id: n for n in db.scalars(select(Node).where(Node.project_id == pid))}
    rows = []
    for it in db.scalars(select(BacklogItem).where(BacklogItem.project_id == pid,
                                                   BacklogItem.status.in_([ItemStatus.approved, ItemStatus.edited]))):
        src = nodes.get(it.source_node_id)
        rows.append({"kind": it.kind, "title": it.title, "parent": it.parent_item_id or "",
                     "source": " > ".join(src.lineage) if src else "", "status": it.status.value,
                     "details": str(it.body)})
    db.commit()  # release read transaction before the closing event write
    emit(pid, "export", "stage_end", f"Exported {len(rows)} validated item(s)",
         {"rows": len(rows)})
    return Response(to_xlsx(rows), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": "attachment; filename=backlog.xlsx"})
