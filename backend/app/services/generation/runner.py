import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.llm.providers import get_llm
from app.models import BacklogItem, Edge, GenerationTrace, Node, Project
from app.services.events import emit

from .prompt import SYSTEM, build_user_prompt

EMPTY_CREATED = {"epics": 0, "stories": 0, "tests": 0, "questions": 0}


def _d(n: Node) -> dict:
    return {"number": n.number, "title": n.title, "text": n.text}


def _validate_response(out) -> None:
    """Reject malformed LLM JSON so the caller can retry once."""
    if not isinstance(out, dict) or not out:
        raise ValueError("LLM response must be a non-empty JSON object")
    epic = out.get("epic")
    if epic is not None and not isinstance(epic, dict):
        raise TypeError("'epic' must be an object")
    for key in ("stories", "tests", "questions"):
        value = out.get(key)
        if value is not None and not isinstance(value, list):
            raise TypeError(f"'{key}' must be a list")
    for key in ("stories", "tests"):
        for entry in out.get(key) or []:
            if not isinstance(entry, dict):
                raise TypeError(f"every entry in '{key}' must be an object")
    for question in out.get("questions") or []:
        if not isinstance(question, str):
            raise TypeError("every question must be a string")


def _neighbours(db: Session, leaf: Node) -> tuple[list[dict], list[dict]]:
    """Return trace neighbours (with score/kind) and prompt neighbours (with text)."""
    edges = db.scalars(
        select(Edge).where(Edge.source_id == leaf.id).order_by(Edge.score.desc())
    ).all()
    node_ids = [edge.target_id for edge in edges]
    nodes = {
        node.id: node
        for node in db.scalars(select(Node).where(Node.id.in_(node_ids)))
    } if node_ids else {}
    trace_neighbours: list[dict] = []
    prompt_neighbours: list[dict] = []
    for edge in edges:
        node = nodes.get(edge.target_id)
        if not node:
            continue
        trace_neighbours.append({
            "node_id": node.id,
            "number": node.number,
            "title": node.title,
            "score": float(edge.score),
            "kind": edge.kind,
        })
        prompt_neighbours.append(_d(node))
    return trace_neighbours, prompt_neighbours


def _persist_items(db: Session, project_id: str, leaf: Node, out: dict) -> dict:
    questions = out.get("questions") or []
    epic_data = out.get("epic") or {}
    epic = BacklogItem(project_id=project_id, source_node_id=leaf.id, kind="epic",
                       title=epic_data.get("title") or leaf.title, questions=questions)
    db.add(epic)
    db.flush()
    story_ids: dict[str, str] = {}
    stories = out.get("stories") or []
    for story in stories:
        item = BacklogItem(project_id=project_id, source_node_id=leaf.id, kind="story",
                           parent_item_id=epic.id, title=story.get("title", ""), body=story)
        db.add(item)
        db.flush()
        story_ids[item.title] = item.id
    tests = out.get("tests") or []
    for test in tests:
        item = BacklogItem(project_id=project_id, source_node_id=leaf.id, kind="test",
                           parent_item_id=story_ids.get(test.get("story_title")),
                           title=test.get("title", ""), body=test)
        db.add(item)
    return {"epics": 1, "stories": len(stories), "tests": len(tests),
            "questions": len(questions)}


def generate_for_leaf(db: Session, project_id: str, leaf: Node, llm) -> GenerationTrace:
    """Generate one leaf, retrying malformed JSON once, and persist its trace + items."""
    trace_neighbours, prompt_neighbours = _neighbours(db, leaf)
    globals_ = db.scalars(
        select(Node).where(Node.project_id == project_id, Node.is_global.is_(True))
    ).all()
    global_ctx = [_d(node) for node in globals_]
    global_ids = [node.id for node in globals_]
    prompt = build_user_prompt(leaf.lineage, leaf.text, prompt_neighbours, global_ctx)

    started = time.perf_counter()
    attempts = 0
    out = None
    first_error: str | None = None
    status = "ok"
    while attempts < 2:  # one automatic retry
        attempts += 1
        out = None
        try:
            out = llm.complete_json(SYSTEM, prompt, {})
            _validate_response(out)
            status = "retried" if attempts > 1 else "ok"
            break
        except Exception as exc:  # noqa: BLE001 - provider errors must be retried/isolated
            # malformed JSON, provider error, timeout...
            message = f"{type(exc).__name__}: {exc}"
            if first_error is None:
                first_error = message
            if attempts >= 2:
                status = "failed"

    duration_ms = int((time.perf_counter() - started) * 1000)
    created = dict(EMPTY_CREATED)
    error = first_error if status in ("failed", "retried") else None
    if status != "failed":
        try:
            created = _persist_items(db, project_id, leaf, out or {})
        except Exception as exc:  # noqa: BLE001 - a broken leaf must not stop the run
            db.rollback()
            status = "failed"
            error = f"{type(exc).__name__}: {exc}"
            created = dict(EMPTY_CREATED)
    else:
        db.rollback()

    if out is None:
        response = None
    elif isinstance(out, (dict, list)):
        response = out
    else:
        response = {"raw": str(out)}
    trace = GenerationTrace(
        project_id=project_id,
        node_id=leaf.id,
        prompt=prompt,
        response_json=response,
        neighbours=trace_neighbours,
        global_context_ids=global_ids,
        duration_ms=duration_ms,
        attempts=attempts,
        status=status,
        error=error,
        items_created=created,
    )
    db.add(trace)
    db.commit()
    return trace


def _latest_status_by_node(db: Session, project_id: str) -> dict[str, str]:
    traces = db.scalars(
        select(GenerationTrace)
        .where(GenerationTrace.project_id == project_id)
        .order_by(GenerationTrace.id)
    ).all()
    return {trace.node_id: trace.status for trace in traces}


def _item_count(created: dict) -> int:
    return sum(created.get(key, 0) for key in ("epics", "stories", "tests"))


def generate_project(db: Session, project: Project, *, only_failed: bool = False) -> int:
    """Generate all (or only previously failed) leaves. A failing leaf never stops the run."""
    project_id = project.id
    llm = get_llm()
    leaves = db.scalars(
        select(Node).where(
            Node.project_id == project_id,
            Node.is_leaf.is_(True),
            Node.is_global.is_(False),
            Node.is_front_matter.is_(False),
        ).order_by(Node.position)
    ).all()
    if only_failed:
        latest = _latest_status_by_node(db, project_id)
        leaves = [leaf for leaf in leaves if latest.get(leaf.id) == "failed"]
    db.commit()  # release the read transaction before emitting events per leaf

    total = len(leaves)
    emit(project_id, "generation", "stage_start",
         f"Generating backlog for {total} leaf sections",
         {"N": total, "only_failed": only_failed})

    count = 0
    failed = 0
    for i, leaf in enumerate(leaves, 1):
        emit(project_id, "generation", "leaf_start",
             f"Leaf {i}/{total}: {leaf.number or leaf.title}",
             {"node_id": leaf.id, "i": i, "N": total})
        if settings.demo_delay_ms > 0:
            time.sleep(settings.demo_delay_ms / 1000.0)
        try:
            trace = generate_for_leaf(db, project_id, leaf, llm)
        except Exception as exc:  # noqa: BLE001 - last-resort isolation: keep the run alive
            db.rollback()
            failed += 1
            message = f"{type(exc).__name__}: {exc}"
            emit(project_id, "generation", "leaf_failed", f"Leaf failed: {message}",
                 {"node_id": leaf.id, "error": message})
            continue

        if trace.status == "failed":
            failed += 1
            emit(project_id, "generation", "leaf_failed",
                 f"Leaf failed after {trace.attempts} attempt(s): {trace.error}",
                 {"node_id": leaf.id, "error": trace.error, "attempts": trace.attempts})
        else:
            count += _item_count(trace.items_created)
            emit(project_id, "generation", "leaf_done",
                 f"Leaf done: {trace.items_created.get('stories', 0)} stories",
                 {"node_id": leaf.id,
                  "epics": trace.items_created.get("epics", 0),
                  "stories": trace.items_created.get("stories", 0),
                  "tests": trace.items_created.get("tests", 0),
                  "questions": trace.items_created.get("questions", 0),
                  "duration_ms": trace.duration_ms,
                  "attempts": trace.attempts})

    project.status = "generated"
    db.commit()
    emit(project_id, "generation", "stage_end",
         f"Generation finished: {count} items, {failed} failed leaf/leaves",
         {"items": count, "leaves": total, "failed": failed,
          "succeeded": total - failed, "only_failed": only_failed})
    return count
