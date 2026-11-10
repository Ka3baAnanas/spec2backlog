"""Meaning graph: leaf-to-leaf links = embedding neighbours + explicit references ("voir §4.1")."""
import re
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.llm.providers import get_embedder
from app.models import Edge, Node, Project
from app.services.events import emit
from app.vectorstore.store import get_store

REF_RE = re.compile(r"(?:voir|cf\.?|section|§)\s*(?:§\s*)?(\d+(?:\.\d+)*)", re.IGNORECASE)


def explicit_refs(text: str) -> set[str]:
    return set(REF_RE.findall(text))


def build_links(project_id: str, leaves: list, *, emit_events: bool = True) -> list[dict]:
    """leaves: TNode/Node-like objects (id, number, title, text). Returns edge dicts."""
    leaves = [leaf for leaf in leaves if not getattr(leaf, "is_front_matter", False)]
    total = len(leaves)
    if emit_events:
        emit(project_id, "graph", "stage_start", f"Embedding {total} leaf sections",
             {"leaves": total})

    emb, store = get_embedder(), get_store()
    vecs = []
    if total:
        texts = [f"{leaf.title}\n{leaf.text}"[: settings.max_leaf_tokens * 4] for leaf in leaves]
        vecs = emb.embed(texts)
        store.upsert(project_id, [leaf.id for leaf in leaves], vecs)

    by_number = {leaf.number: leaf for leaf in leaves if leaf.number}
    edges: list[dict] = []
    linked: set[str] = set()
    for i, (leaf, vec) in enumerate(zip(leaves, vecs), 1):
        if emit_events:
            emit(project_id, "graph", "progress",
                 f"Embedded {i}/{total}: {leaf.title}",
                 {"i": i, "N": total, "node_id": leaf.id, "number": leaf.number,
                  "title": leaf.title})
        leaf_edges: list[dict] = []
        for nid, score in store.neighbours(project_id, vec, settings.similar_top_k,
                                           exclude=leaf.id):
            if score >= settings.similar_min_score:
                leaf_edges.append({"source_id": leaf.id, "target_id": nid,
                                   "kind": "similarity", "score": float(score)})
        for num in explicit_refs(leaf.text):
            tgt = by_number.get(num)
            if tgt and tgt.id != leaf.id:
                leaf_edges.append({"source_id": leaf.id, "target_id": tgt.id,
                                   "kind": "reference", "score": 1.0})
        for edge in leaf_edges:
            edges.append(edge)
            linked.add(leaf.id)
            linked.add(edge["target_id"])
            if emit_events:
                emit(project_id, "graph", "link_found",
                     f"{leaf.number or leaf.title} → {edge['target_id']} ({edge['kind']})",
                     {"source_id": edge["source_id"], "target_id": edge["target_id"],
                      "kind": edge["kind"], "score": edge["score"]})

    by_kind = dict(Counter(edge["kind"] for edge in edges))
    zero_link = [leaf.id for leaf in leaves if leaf.id not in linked]
    summary = {"leaves": total, "edges": len(edges), "edges_by_kind": by_kind,
               "leaves_with_zero_links": len(zero_link), "zero_link_node_ids": zero_link}
    if emit_events:
        emit(project_id, "graph", "stage_end",
             f"Graph built: {len(edges)} links across {total} leaves",
             summary)
    return edges


def build_graph_for_project(db: Session, project: Project, *, emit_events: bool = True) -> dict:
    """Rebuild the persisted meaning graph for a project. Emits graph events."""
    project_id = project.id
    leaves = db.scalars(
        select(Node).where(
            Node.project_id == project_id,
            Node.is_leaf.is_(True),
            Node.is_front_matter.is_(False),
        )
    ).all()
    db.query(Edge).filter(Edge.project_id == project_id).delete()
    db.commit()  # release SQLite write lock before background-friendly event writes

    try:
        edges = build_links(project_id, leaves, emit_events=emit_events)
    except Exception as exc:
        emit(project_id, "graph", "error",
             f"Graph stage failed: {type(exc).__name__}: {exc}", {"error": str(exc)})
        raise
    for edge in edges:
        db.add(Edge(project_id=project_id, **edge))
    project.status = "graph_built"
    db.commit()
    return {"leaves": len(leaves), "edges": len(edges)}
