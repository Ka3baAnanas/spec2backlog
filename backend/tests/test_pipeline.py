import json
import time
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.db import SessionLocal
from app.domain.models import GenerationTrace
from app.main import app
from app.modules.generation import service as generation_service
from app.modules.knowledge.retriever import explicit_refs
from app.modules.structure.tree import is_front_matter_title
from app.providers.llm.fake import FakeLLM

SAMPLE = Path(__file__).resolve().parents[2] / "samples" / "exemple_specifications.docx"
client = TestClient(app)


def _upload(name: str = "demo") -> str:
    response = client.post(
        "/api/v1/projects",
        data={"name": name},
        files={"file": (SAMPLE.name, SAMPLE.read_bytes())},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _sections(pid: str) -> list[dict]:
    response = client.get(f"/api/v1/projects/{pid}/sections")
    assert response.status_code == 200, response.text
    return response.json()


def _wait(pid: str, timeout: float = 40) -> dict:
    deadline = time.time() + timeout
    last = {}
    while time.time() < deadline:
        response = client.get(f"/api/v1/projects/{pid}/pipeline/status")
        assert response.status_code == 200, response.text
        last = response.json()
        run = last.get("run") or {}
        if last["status"] != "generating" and run.get("status") in (None, "finished"):
            return last
        time.sleep(0.1)
    raise AssertionError(f"pipeline did not finish: {last}")


def _approve_and_generate(pid: str) -> dict:
    assert client.post(f"/api/v1/projects/{pid}/pipeline/approve-context").status_code == 200
    response = client.post(f"/api/v1/projects/{pid}/pipeline/generate")
    assert response.status_code == 200, response.text
    return _wait(pid)


def test_health_and_provider_flags():
    assert client.get("/api/v1/health").json() == {"ok": True}
    providers = client.get("/api/v1/settings/providers").json()
    assert providers["offline_demo"] is True
    assert providers["llm"]["fake"] is True
    assert providers["embeddings"]["fake"] is True


def test_upload_auto_prepares_document_structure_and_links():
    pid = _upload("auto-prepare")
    project = client.get(f"/api/v1/projects/{pid}").json()
    assert project["status"] == "awaiting_context_approval"
    assert project["context_approved"] is False

    document = client.get(f"/api/v1/projects/{pid}/document").json()
    assert document["stats"]["headings"] > 0
    assert document["stats"]["preview"]
    assert "missing" in document["checklist"]

    sections = _sections(pid)
    assert sum(1 for section in sections if section["role"] == "requirement") > 5
    assert any(section["role"] == "context" for section in sections)

    links = client.get(f"/api/v1/projects/{pid}/links").json()
    assert links
    assert {"similarity", "reference", "lexical"}.intersection({link["kind"] for link in links})


def test_generation_is_gated_until_context_approval():
    pid = _upload("gating")
    response = client.post(f"/api/v1/projects/{pid}/pipeline/generate")
    assert response.status_code == 409
    assert "approved" in response.json()["detail"].lower()


def test_full_happy_path_fake_mode():
    pid = _upload("happy-path")
    sections = _sections(pid)
    requirements = [section for section in sections if section["role"] == "requirement"]
    assert requirements

    status = _approve_and_generate(pid)
    assert status["status"] == "generated", status
    assert status["context_approved"] is True

    backlog = client.get(f"/api/v1/projects/{pid}/backlog").json()
    assert backlog["stats"]["epics"] > 0
    assert backlog["stats"]["stories"] > 0
    assert backlog["stats"]["tests"] > 0

    for epic in backlog["epics"]:
        assert epic["key"].startswith("EP-")
        for story in epic["stories"]:
            assert story["key"].startswith("US-")
            assert story["body"]["acceptance_criteria"]
            assert story["body"]["quality"]["has_test"] is True
            assert story["tests"]
            for test in story["tests"]:
                assert test["key"].startswith("TC-")

    coverage = client.get(f"/api/v1/projects/{pid}/coverage").json()
    assert coverage["coverage"] > 0
    assert coverage["rows"]

    xlsx = client.get(f"/api/v1/projects/{pid}/export", params={"format": "xlsx"})
    assert xlsx.status_code == 200 and xlsx.content[:2] == b"PK"

    approved = client.post(f"/api/v1/projects/{pid}/backlog/approve")
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    csv_response = client.get(f"/api/v1/projects/{pid}/export", params={"format": "csv"})
    assert csv_response.status_code == 200
    assert b"key,kind,title" in csv_response.content[:20]
    assert client.get(f"/api/v1/projects/{pid}").json()["status"] == "exported"

    first = requirements[0]
    preview = client.get(f"/api/v1/sections/{first['id']}/context").json()
    with SessionLocal() as db:
        trace = db.scalars(
            select(GenerationTrace)
            .where(GenerationTrace.section_id == first["id"])
            .order_by(GenerationTrace.id.desc())
        ).first()
    assert trace is not None
    assert trace.prompt == preview["prompt"]


def test_role_change_excludes_section_from_generation():
    pid = _upload("role-change")
    sections = _sections(pid)
    requirement = next(section for section in sections if section["role"] == "requirement")
    response = client.patch(f"/api/v1/sections/{requirement['id']}", json={"role": "context"})
    assert response.status_code == 200, response.text
    assert response.json()["role"] == "context"

    status = _approve_and_generate(pid)
    assert status["status"] == "generated", status

    backlog = client.get(f"/api/v1/projects/{pid}/backlog").json()
    source_ids = set()
    for epic in backlog["epics"]:
        source_ids.add(epic["source_section_id"])
        for story in epic["stories"]:
            source_ids.add(story["source_section_id"])
            source_ids.update(story["source_sections"])
    assert requirement["id"] not in source_ids


def test_disabled_link_disappears_from_prompt_preview():
    pid = _upload("disabled-link")
    sections = _sections(pid)
    requirements = [section for section in sections if section["role"] == "requirement"]
    source, target = requirements[0], requirements[1]
    marker = f"[{target['number']} {target['title']}]"

    link = client.post(
        f"/api/v1/projects/{pid}/links",
        json={
            "source_id": source["id"],
            "target_id": target["id"],
            "kind": "manual",
            "reason": "test link",
        },
    )
    assert link.status_code == 200, link.text
    link_id = link.json()["id"]

    before = client.get(f"/api/v1/sections/{source['id']}/context").json()
    assert marker in before["prompt"]
    assert any(item["section_id"] == target["id"] for item in before["links"])

    disabled = client.patch(f"/api/v1/links/{link_id}", json={"enabled": False})
    assert disabled.status_code == 200, disabled.text

    # Disable every other link between the same pair so the assertion isolates this link.
    for candidate in client.get(f"/api/v1/projects/{pid}/links").json():
        pair = {candidate["source_id"], candidate["target_id"]}
        if pair == {source["id"], target["id"]} and candidate["enabled"]:
            assert client.patch(
                f"/api/v1/links/{candidate['id']}", json={"enabled": False}
            ).status_code == 200

    after = client.get(f"/api/v1/sections/{source['id']}/context").json()
    assert marker not in after["prompt"]
    assert all(item["section_id"] != target["id"] for item in after["links"])


def test_ask_returns_answer_with_citations():
    pid = _upload("ask")
    response = client.post(
        f"/api/v1/projects/{pid}/ask",
        json={"question": "Quelles sont les exigences fonctionnelles ?"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["answer"]
    assert payload["citations"]
    section_ids = {section["id"] for section in _sections(pid)}
    assert all(citation["section_id"] in section_ids for citation in payload["citations"])


def test_stubs_return_501():
    pid = _upload("stubs")
    for fmt in ("jira", "azure"):
        response = client.get(f"/api/v1/projects/{pid}/export", params={"format": fmt})
        assert response.status_code == 501, response.text
        assert "not implemented" in response.json()["detail"].lower()

    response = client.post(f"/api/v1/projects/{pid}/versions")
    assert response.status_code == 501
    assert "not implemented" in response.json()["detail"].lower()


def test_events_history_and_sse():
    pid = _upload("events")
    history = client.get(f"/api/v1/projects/{pid}/events/history").json()
    assert history
    ids = [event["id"] for event in history]
    assert ids == sorted(ids)
    stages = {event["stage"] for event in history}
    assert {"ingestion", "structure", "knowledge", "context"}.issubset(stages)

    seen: list[int] = []
    payloads: list[dict] = []
    with client.stream(
        "GET", f"/api/v1/projects/{pid}/events", headers={"Last-Event-ID": "0"}
    ) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        for line in response.iter_lines():
            if line.startswith("id: "):
                seen.append(int(line[4:]))
            elif line.startswith("data: "):
                payloads.append(json.loads(line[6:]))
            if len(payloads) >= 2:
                break
    assert seen == sorted(seen)
    assert payloads[0]["project_id"] == pid


def test_failed_run_can_be_retried(monkeypatch):
    pid = _upload("retry")

    class FailingLLM:
        def complete_json(self, system, user, schema):
            raise ValueError("simulated provider failure")

    monkeypatch.setattr(generation_service, "get_llm", lambda: FailingLLM())
    status = _approve_and_generate(pid)
    assert status["status"] == "failed"
    assert status["error"]

    monkeypatch.setattr(generation_service, "get_llm", lambda: FakeLLM())
    retry = client.post(f"/api/v1/projects/{pid}/pipeline/retry-failed")
    assert retry.status_code == 200, retry.text
    status = _wait(pid)
    assert status["status"] == "generated", status
    backlog = client.get(f"/api/v1/projects/{pid}/backlog").json()
    assert backlog["stats"]["stories"] > 0


def test_refs_and_front_matter_heuristics():
    assert explicit_refs("voir §4.1 et cf. 6.3") == {"4.1", "6.3"}
    assert is_front_matter_title("Table des matières")
    assert is_front_matter_title("Historique des versions")
    assert not is_front_matter_title("Validation des données")
