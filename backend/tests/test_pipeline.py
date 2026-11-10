import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.llm.providers import FakeLLM
from app.main import app
from app.services.generation import runner as runner_module
from app.services.graph.builder import explicit_refs
from app.services.ingestion.pivot import Block, PivotDocument
from app.services.tree.builder import build_tree, is_front_matter_title

SAMPLE = Path(__file__).resolve().parents[2] / "samples" / "exemple_specifications.docx"
c = TestClient(app)


def _upload(name: str = "demo") -> str:
    r = c.post("/api/v1/projects/upload", data={"name": name},
               files={"file": (SAMPLE.name, SAMPLE.read_bytes())})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _events(pid: str, after: int = 0) -> list[dict]:
    r = c.get(f"/api/v1/projects/{pid}/events.json", params={"after": after})
    assert r.status_code == 200, r.text
    return r.json()


def test_refs():
    assert explicit_refs("voir §4.1 et cf. 6.3") == {"4.1", "6.3"}


def test_front_matter_detection():
    assert is_front_matter_title("Table des matières")
    assert is_front_matter_title("Historique des versions")
    assert is_front_matter_title("Validation")
    assert is_front_matter_title("Sommaire")
    assert not is_front_matter_title("Validation des données")
    doc = PivotDocument(blocks=[
        Block("heading", "Table des matières", 1),
        Block("paragraph", "1. Intro .... 2"),
        Block("heading", "4.1 Fonction", 1),
        Block("paragraph", "Real text"),
    ])
    ids = iter(range(100))
    tree = build_tree(doc, lambda: f"n{next(ids)}")
    front = [n for n in tree.values() if n.is_front_matter]
    assert len(front) == 1 and front[0].title == "Table des matières"


def test_events_are_emitted_in_order():
    pid = _upload("events")
    events = _events(pid)
    assert events
    ids = [event["id"] for event in events]
    assert ids == sorted(ids)
    stages = [event["stage"] for event in events]
    assert stages[0] == "ingestion"
    assert "tree" in stages
    assert max(i for i, stage in enumerate(stages) if stage == "ingestion") < \
        min(i for i, stage in enumerate(stages) if stage == "tree")

    r = c.post(f"/api/v1/projects/{pid}/graph")
    assert r.status_code == 200, r.text
    later = _events(pid, after=ids[-1])
    assert later and all(event["id"] > ids[-1] for event in later)
    graph_types = {event["type"] for event in later if event["stage"] == "graph"}
    assert {"stage_start", "progress", "stage_end"}.issubset(graph_types)
    summary = next(event for event in later
                   if event["stage"] == "graph" and event["type"] == "stage_end")
    assert "edges_by_kind" in summary["data"]
    assert "leaves_with_zero_links" in summary["data"]


def test_sse_streams_events():
    pid = _upload("sse")
    ids: list[int] = []
    payloads: list[dict] = []
    with c.stream("GET", f"/api/v1/projects/{pid}/events",
                  headers={"Last-Event-ID": "0"}) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        for line in response.iter_lines():
            if line.startswith("id: "):
                ids.append(int(line[4:]))
            elif line.startswith("data: "):
                payloads.append(json.loads(line[6:]))
            if len(payloads) >= 2:
                break
    assert ids and ids == sorted(ids)
    assert payloads[0]["project_id"] == pid


def test_failing_leaf_does_not_stop_run(monkeypatch):
    pid = _upload("failing-leaf")
    tree = c.get(f"/api/v1/projects/{pid}/tree").json()
    leaves = [node for node in tree if node["is_leaf"] and node["text"].strip()
              and not node.get("is_global") and not node.get("is_front_matter")]
    assert len(leaves) >= 2
    bad = leaves[0]
    marker = bad["text"][:60].strip() or bad["title"]

    class OneBrokenLeafLLM:
        def complete_json(self, system, user, schema):
            if marker in user:
                raise ValueError("simulated malformed JSON")
            return {"epic": {"title": "Demo epic"}, "stories": [], "tests": [],
                    "questions": []}

    monkeypatch.setattr(runner_module, "get_llm", lambda: OneBrokenLeafLLM())
    r = c.post(f"/api/v1/projects/{pid}/run", params={"stages": "generate"})
    assert r.status_code == 200, r.text
    assert r.json()["run_id"]

    deadline = time.time() + 20
    events: list[dict] = []
    while time.time() < deadline:
        events = _events(pid)
        if any(event["stage"] == "generation" and event["type"] == "stage_end"
               for event in events):
            break
        time.sleep(0.1)
    assert any(event["stage"] == "generation" and event["type"] == "stage_end"
               for event in events), "background run did not finish"

    types = [event["type"] for event in events if event["stage"] == "generation"]
    assert "leaf_failed" in types
    assert "leaf_done" in types
    failed_event = next(event for event in events
                        if event["type"] == "leaf_failed")
    assert failed_event["data"]["node_id"] == bad["id"]

    trace = c.get(f"/api/v1/projects/{pid}/leaves/{bad['id']}/trace").json()
    assert trace["status"] == "failed"
    assert trace["attempts"] == 2
    assert trace["error"]
    assert trace["prompt"]
    assert trace["neighbours"] == []

    assert c.get(f"/api/v1/projects/{pid}/items").json()

    monkeypatch.setattr(runner_module, "get_llm", lambda: FakeLLM())
    retry = c.post(f"/api/v1/projects/{pid}/generate", params={"only_failed": "true"})
    assert retry.status_code == 200, retry.text
    assert retry.json()["items"] >= 1
    retried_trace = c.get(f"/api/v1/projects/{pid}/leaves/{bad['id']}/trace").json()
    assert retried_trace["status"] == "ok"


def test_end_to_end():
    r = c.post("/api/v1/projects/upload", data={"name": "demo"}, files={"file": (SAMPLE.name, SAMPLE.read_bytes())})
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    tree = c.get(f"/api/v1/projects/{pid}/tree").json()
    assert sum(n["is_leaf"] for n in tree) > 5
    g = c.post(f"/api/v1/projects/{pid}/graph").json()
    assert g["leaves"] > 5
    assert c.post(f"/api/v1/projects/{pid}/generate").status_code == 200
    items = c.get(f"/api/v1/projects/{pid}/items").json()
    assert items
    c.patch(f"/api/v1/items/{items[0]['id']}", json={"status": "approved"})
    x = c.get(f"/api/v1/projects/{pid}/export.xlsx")
    assert x.status_code == 200 and x.content[:2] == b"PK"
