import json
import time
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from docx import Document as DocxDocument
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import func, select

from app.core.config import settings
from app.core.db import SessionLocal
from app.domain.models import BacklogItem, GenerationTrace, Project, Question
from app.main import app
from app.modules.generation import service as generation_service
from app.modules.generation.consolidator import _collect_questions
from app.modules.generation.generator import GenerationResult
from app.modules.generation.prompts import load_template
from app.modules.generation.quality import _story_checks
from app.modules.generation.schema import validate_output
from app.modules.knowledge.retriever import explicit_refs, prune_links
from app.modules.structure.tree import is_front_matter_title
from app.providers.errors import ProviderConfigurationError, ProviderUnavailableError
from app.providers.factory import get_llm, provider_info
from app.providers.llm import openai_compat
from app.providers.llm.fake import FakeLLM
from app.providers.llm.gemini import GeminiLLM

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
    assert document["blocks"]
    assert any(block["kind"] == "heading" for block in document["blocks"])
    assert len([block for block in document["blocks"] if block["kind"] == "table"]) == document["stats"]["tables"]
    assert len(document["skipped"]) == document["stats"]["skipped_toc"]
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
            assert story["body"]["quality"]["has_tests"] is True
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

    story = next(
        story for epic in backlog["epics"] for story in epic["stories"]
    )
    item_trace = client.get(f"/api/v1/items/{story['id']}/trace")
    assert item_trace.status_code == 200, item_trace.text
    assert item_trace.json()["prompt"]
    assert item_trace.json()["response_json"]


def test_manual_context_is_editable_deletable_and_reaches_prompts():
    pid = _upload("manual-context")
    requirement = next(section for section in _sections(pid) if section["role"] == "requirement")

    created = client.post(
        f"/api/v1/projects/{pid}/manual-context",
        json={"title": "Client constraints", "text": "SSO is mandatory on every portal."},
    )
    assert created.status_code == 201, created.text
    manual = created.json()
    assert manual["role"] == "context"
    assert manual["source"] == "manual"
    assert manual["title"] == "Client constraints"

    prompt = client.get(f"/api/v1/sections/{requirement['id']}/context").json()["prompt"]
    assert "SSO is mandatory on every portal." in prompt

    updated = client.patch(
        f"/api/v1/sections/{manual['id']}/manual-context",
        json={"title": "Security constraints", "text": "MFA is mandatory."},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["title"] == "Security constraints"

    prompt = client.get(f"/api/v1/sections/{requirement['id']}/context").json()["prompt"]
    assert "MFA is mandatory." in prompt
    assert "SSO is mandatory" not in prompt

    deleted = client.delete(f"/api/v1/sections/{manual['id']}/manual-context")
    assert deleted.status_code == 200, deleted.text
    assert all(section["id"] != manual["id"] for section in _sections(pid))

    prompt = client.get(f"/api/v1/sections/{requirement['id']}/context").json()["prompt"]
    assert "MFA is mandatory." not in prompt


def test_graph_links_are_pruned_by_score_and_degree():
    pid = _upload("graph-pruning")
    links = client.get(f"/api/v1/projects/{pid}/links").json()
    assert links
    assert all(link["score"] >= settings.graph_min_link_score for link in links)

    degree: dict[str, int] = {}
    for link in links:
        degree[link["source_id"]] = degree.get(link["source_id"], 0) + 1
        degree[link["target_id"]] = degree.get(link["target_id"], 0) + 1
    assert max(degree.values()) <= settings.graph_max_links_per_node

    synthetic = [
        {"source_id": "a", "target_id": "b", "kind": "similarity", "score": 0.62},
        {"source_id": "a", "target_id": "b", "kind": "lexical", "score": 0.9},
        {"source_id": "a", "target_id": "c", "kind": "lexical", "score": 0.2},
    ]
    kept = prune_links(synthetic)
    assert [(link["source_id"], link["target_id"], link["kind"]) for link in kept] == [
        ("a", "b", "similarity")
    ]


def test_extra_instructions_are_saved_and_appended_to_the_prompt():
    pid = _upload("extra-instructions")
    requirement = next(section for section in _sections(pid) if section["role"] == "requirement")

    response = client.patch(
        f"/api/v1/sections/{requirement['id']}",
        json={"extra_instructions": "Always mention the audit trail."},
    )
    assert response.status_code == 200, response.text
    assert response.json()["extra_instructions"] == "Always mention the audit trail."

    context = client.get(f"/api/v1/sections/{requirement['id']}/context").json()
    assert context["instructions"]
    assert context["tokens"] > 0
    assert "Always mention the audit trail." in context["prompt"]
    assert "HUMAN INSTRUCTION:" in context["prompt"]


def test_two_pass_generation_builds_detailed_epic_feature_story_hierarchy():
    pid = _upload("two-pass")
    status = _approve_and_generate(pid)
    assert status["status"] == "generated", status

    backlog = client.get(f"/api/v1/projects/{pid}/backlog").json()
    assert 5 <= backlog["stats"]["epics"] <= 9
    assert backlog["stats"]["features"] > 0
    assert backlog["stats"]["stories"] > 0

    for epic in backlog["epics"]:
        assert epic["key"].startswith("EP-")
        assert epic["body"]["summary"]
        assert epic["features"]
        for feature in epic["features"]:
            assert feature["key"].startswith("FT-")
            assert feature["stories"]
            for story in feature["stories"]:
                body = story["body"]
                assert story["key"].startswith("US-")
                assert story["title"]
                assert not story["title"].lower().startswith("handle ")
                assert "objet" not in story["title"].lower()
                assert body["persona"]
                assert body["goal"].startswith("to ")
                assert "to to " not in body["goal"].lower()
                assert body["benefit"]
                assert len(body["description"]) > 80
                assert body["business_rules"]
                assert 3 <= len(body["acceptance_criteria"]) <= 5
                assert body["priority"] in ("must", "should", "could")
                assert body["priority_reason"]
                assert body["estimate"] in ("S", "M", "L")
                assert body["dependencies"]
                assert 3 <= len(story["tests"]) <= 5
                assert all(not test["title"].startswith("Verify ") for test in story["tests"])
                assert all(test["title"] != "Reject an incomplete item" for test in story["tests"])
                assert body["source_evidence"]
                assert "confidence" not in body
                for test in story["tests"]:
                    assert test["key"].startswith("TC-")
                    assert test["title"]
                    assert test["body"]["preconditions"]
                    assert test["body"]["steps"]
                    assert test["body"]["test_data"]
                    assert test["body"]["expected"]
                assert story["confidence"] > 0


def test_questions_are_deduplicated_and_keep_highest_priority():
    results = [
        GenerationResult(
            section_id="section-1",
            status="ok",
            output={"questions": [{"text": "Who approves the release?", "priority": "Minor"}]},
        ),
        GenerationResult(
            section_id="section-2",
            status="ok",
            output={"questions": [{"text": "who approves the release", "priority": "Blocking"}]},
        ),
    ]
    questions = _collect_questions(results)
    assert len(questions) == 1
    assert questions[0]["text"] == "Who approves the release?"
    assert questions[0]["priority"] == "Blocking"
    assert questions[0]["section_id"] == "section-1"


def test_excel_and_word_exports_contain_approved_items_and_validation_report():
    pid = _upload("exports")
    _approve_and_generate(pid)
    backlog = client.get(f"/api/v1/projects/{pid}/backlog").json()
    rejected_story = next(
        story for epic in backlog["epics"] for story in epic["stories"]
    )
    rejected = client.patch(
        f"/api/v1/items/{rejected_story['id']}",
        json={"status": "rejected", "by": "qa-reviewer"},
    )
    assert rejected.status_code == 200, rejected.text
    assert client.post(f"/api/v1/projects/{pid}/backlog/approve").status_code == 200

    xlsx = client.get(f"/api/v1/projects/{pid}/export", params={"format": "xlsx"})
    assert xlsx.status_code == 200, xlsx.text
    workbook = load_workbook(BytesIO(xlsx.content))
    assert workbook.sheetnames == [
        "Epics", "Features", "Stories", "Acceptance criteria", "Test cases",
        "Traceability matrix", "Open questions", "Validation report",
    ]
    stories_sheet = workbook["Stories"]
    assert stories_sheet.freeze_panes == "A2"
    assert stories_sheet.auto_filter.ref
    assert stories_sheet["A1"].font.bold is True
    story_keys = {
        row[0].value for row in stories_sheet.iter_rows(min_row=2, max_col=1)
    }
    assert rejected_story["key"] not in story_keys

    validation_sheet = workbook["Validation report"]
    validation_keys = {
        row[0].value for row in validation_sheet.iter_rows(min_row=2, max_col=1)
    }
    assert rejected_story["key"] in validation_keys

    docx = client.get(f"/api/v1/projects/{pid}/export", params={"format": "docx"})
    assert docx.status_code == 200, docx.text
    document = DocxDocument(BytesIO(docx.content))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "Backlog document" in text
    assert "Traceability matrix" in text
    assert "Open questions" in text
    assert "Validation report" in text
    assert document.tables


def test_goal_and_benefit_are_normalized_for_llm_responses():
    output = validate_output(
        {
            "stories": [
                {
                    "title": "Normalize wording",
                    "persona": "Business Analyst",
                    "goal": "To To See the release scope",
                    "benefit": "To Avoid rework",
                    "acceptance_criteria": ["Given a scope, when it changes, then it is recorded."],
                }
            ]
        }
    )
    story = output["stories"][0]
    assert story["goal"] == "to see the release scope"
    assert story["benefit"] == "avoid rework"
    assert story["i_want"] == "to see the release scope"
    assert story["so_that"] == "avoid rework"


def test_confidence_penalizes_short_evidence_and_uncovered_tests():
    story = BacklogItem(
        title="Thin story",
        kind="story",
        body={
            "acceptance_criteria": [
                "Given a, when b, then the record is saved.",
                "Given a, when b, then the approver is notified.",
                "Given a, when b, then the export is blocked.",
            ],
            "source_evidence": ["Only one quote"],
            "ambiguity_flag": False,
        },
    )
    test = BacklogItem(
        title="Unrelated check",
        kind="test",
        body={"expected": "Something completely different."},
    )
    checks = _story_checks(story, [test])
    assert checks["has_source_evidence"] is False
    assert checks["tests_cover_criteria"] is False
    assert checks["has_acceptance_criteria"] is True
    assert checks["has_tests"] is True
    assert checks["no_ambiguity_flag"] is True


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


def test_interrupted_run_can_be_resumed():
    pid = _upload("resume")
    _approve_and_generate(pid)

    with SessionLocal() as db:
        trace = db.scalars(
            select(GenerationTrace).where(GenerationTrace.project_id == pid)
        ).first()
        assert trace is not None
        db.delete(trace)
        db.query(BacklogItem).filter(BacklogItem.project_id == pid).delete()
        project = db.get(Project, pid)
        project.status = "generating"
        db.commit()

    response = client.post(f"/api/v1/projects/{pid}/pipeline/recover")
    assert response.status_code == 200, response.text
    assert response.json()["resume"] is True

    status = _wait(pid)
    assert status["status"] == "generated", status
    backlog = client.get(f"/api/v1/projects/{pid}/backlog").json()
    assert backlog["stats"]["stories"] > 0


def test_refs_and_front_matter_heuristics():
    assert explicit_refs("voir §4.1 et cf. 6.3") == {"4.1", "6.3"}
    assert is_front_matter_title("Table des matières")
    assert is_front_matter_title("Historique des versions")
    assert not is_front_matter_title("Validation des données")


def test_output_schema_coerces_real_llm_shapes():
    output = validate_output(
        {
            "epic": "Password reset",
            "stories": [
                {
                    "title": "Reset a password",
                    "acceptance_criteria": "Given a user, when they reset, then it works",
                }
            ],
            "tests": [{"title": "Reset test", "steps": [{"step": "Open the reset page"}]}],
            "questions": [{"question": "What is the token lifetime?"}],
        }
    )
    assert output["epic"]["title"] == "Password reset"
    assert output["stories"][0]["acceptance_criteria"] == [
        "Given a user, when they reset, then it works"
    ]
    assert output["stories"][0]["tests"][0]["steps"] == ["Open the reset page"]
    assert output["questions"][0]["text"] == "What is the token lifetime?"


def test_generation_prompts_force_english_output():
    system = load_template("system")
    user = load_template("user")
    consolidate_system = load_template("consolidate_system")
    consolidate_user = load_template("consolidate_user")

    assert "ALWAYS answer in English" in system
    assert "Never mix languages inside a field" in system
    assert "Given/When/Then statements in English" in system
    assert "OUTPUT LANGUAGE: English" in user
    assert "ALWAYS write every field in English" in consolidate_system
    assert "OUTPUT LANGUAGE: English" in consolidate_user


def test_openai_compat_retries_rate_limit(monkeypatch):
    monkeypatch.setattr(settings, "llm_retry_base_seconds", 0.0)
    monkeypatch.setattr(settings, "llm_retry_max_seconds", 0.0)
    events = []
    calls = []

    def fake_post(*args, **kwargs):
        calls.append(kwargs)
        request = httpx.Request("POST", "http://test/chat/completions")
        if len(calls) == 1:
            return httpx.Response(429, headers={"retry-after": "0"}, request=request)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"ok": true}'}}]},
            request=request,
        )

    monkeypatch.setattr(openai_compat.httpx, "post", fake_post)
    llm = openai_compat.OpenAICompatLLM(base_url="http://test", api_key="", model="m")

    result = llm.complete_json("system", "user", {}, on_event=lambda *args: events.append(args))

    assert result == {"ok": True}
    assert len(calls) == 2
    assert events[0][0] == "warning"


def test_configured_provider_failure_never_uses_fake_llm(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "llm_fallback_provider", "")

    with pytest.raises(ProviderConfigurationError):
        get_llm()

    info = provider_info()
    assert info["llm"]["active"] == "unavailable"
    assert info["llm"]["fake"] is False
    assert info["llm"]["error"]


def test_gemini_provider_failure_does_not_switch_to_demo(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "key")
    monkeypatch.setattr(settings, "llm_model", "gemini-a")
    monkeypatch.setattr(settings, "gemini_fallback_model", "gemini-b")
    events = []

    def offline(*args, **kwargs):
        raise ProviderUnavailableError("offline")

    monkeypatch.setattr("app.providers.llm.gemini.post_with_retry", offline)
    llm = GeminiLLM()

    with pytest.raises(ProviderUnavailableError):
        llm.complete_json("system", "user", {}, on_event=lambda *args: events.append(args))

    assert not any("demo" in str(event).lower() for event in events)


def test_retryable_generation_failure_waits_without_publishing_backlog(monkeypatch):
    pid = _upload("retryable")
    assert client.post(f"/api/v1/projects/{pid}/pipeline/approve-context").status_code == 200
    monkeypatch.setattr(generation_service.settings, "use_celery", True)
    monkeypatch.setattr(generation_service.settings, "celery_task_max_retries", 3)
    monkeypatch.setattr(generation_service.settings, "celery_retry_backoff_seconds", 0.0)
    monkeypatch.setattr(generation_service.settings, "celery_retry_max_backoff_seconds", 0.0)

    class OfflineLLM:
        def complete_json(self, system, user, schema, **kwargs):
            raise ProviderUnavailableError("network down")

    monkeypatch.setattr(generation_service, "get_llm", lambda: OfflineLLM())

    with SessionLocal() as db:
        project = db.get(Project, pid)
        result = generation_service.run_generation(db, project, run_id="retry-run")

    assert result["retry_requested"] is True
    assert result["failed"] > 0
    assert result["retryable_failed"] == result["failed"]
    assert result["retry_in"] == 0.0
    backlog = client.get(f"/api/v1/projects/{pid}/backlog").json()
    assert backlog["stats"]["stories"] == 0


def test_consolidation_failure_waits_without_partial_backlog(monkeypatch):
    pid = _upload("consolidate-retry")
    assert client.post(f"/api/v1/projects/{pid}/pipeline/approve-context").status_code == 200
    monkeypatch.setattr(generation_service.settings, "use_celery", True)
    monkeypatch.setattr(generation_service.settings, "celery_task_max_retries", 3)
    monkeypatch.setattr(generation_service.settings, "celery_retry_backoff_seconds", 0.0)
    monkeypatch.setattr(generation_service.settings, "celery_retry_max_backoff_seconds", 0.0)

    def offline_consolidate(*args, **kwargs):
        raise ProviderUnavailableError("consolidation offline")

    monkeypatch.setattr(generation_service, "consolidate", offline_consolidate)

    with SessionLocal() as db:
        project = db.get(Project, pid)
        result = generation_service.run_generation(db, project, run_id="consolidate-run")

    assert result["retry_requested"] is True
    assert result["failed"] == 0
    backlog = client.get(f"/api/v1/projects/{pid}/backlog").json()
    assert backlog["stats"]["stories"] == 0


def test_resume_reuses_completed_traces():
    pid = _upload("resume-reuse")
    _approve_and_generate(pid)

    with SessionLocal() as db:
        before = db.scalar(
            select(func.count(GenerationTrace.id)).where(
                GenerationTrace.project_id == pid
            )
        )
        trace = db.scalars(
            select(GenerationTrace).where(GenerationTrace.project_id == pid)
        ).first()
        assert trace is not None
        db.delete(trace)
        db.query(BacklogItem).filter(BacklogItem.project_id == pid).delete()
        db.query(Question).filter(Question.project_id == pid).delete()
        project = db.get(Project, pid)
        project.status = "generating"
        db.commit()

    with SessionLocal() as db:
        project = db.get(Project, pid)
        result = generation_service.run_generation(db, project, run_id="resume-reuse", resume=True)

    assert result["resume"] is True
    assert result["succeeded"] == before
    with SessionLocal() as db:
        after = db.scalar(
            select(func.count(GenerationTrace.id)).where(
                GenerationTrace.project_id == pid
            )
        )
    assert after == before
