# Architecture

The source of truth is [`BLUEPRINT.md`](BLUEPRINT.md). This document explains how the code implements it.

## 1. Workflow (end to end)

```
Upload .docx/.pdf
  1 INGESTION   extract text + headings + tables -> PIVOT format
                (completeness checklist, warnings, OCR stub for scanned PDFs)
  2 STRUCTURE   headings = tree nodes; text under the last heading belongs to that node;
                each section gets a role: requirement | context | glossary | front_matter | ignored
  3 KNOWLEDGE   hybrid links between leaves: vector similarity + explicit references
                ("voir §4.1") + lexical keyword overlap (reason + score per link);
                glossary extraction
  -- human checkpoint 1: approve the context --
  4 GENERATION  one LLM call per requirement leaf using the exact context pack;
                JSON validation + one retry; generation trace saved; consolidation merges
                near-duplicate stories across leaves and assigns EP-01 / US-001 / TC-001 keys;
                quality checks (criteria + at least one test, confidence)
  5 REVIEW      BA approves / edits / rejects with an audit trail; regenerate one item
  6 EXPORT      Excel / CSV + traceability matrix + coverage %; Jira / Azure DevOps are stubs
```

Project status: `uploaded -> parsed -> structured -> linked -> awaiting_context_approval -> generating ->
generated -> in_review -> approved -> exported` (+ `failed` with a reason). Parse, structure and link are
run automatically by upload (`prepare`).

## 2. Stack and why

| Layer | Choice | Why |
|---|---|---|
| Backend | Python 3.11+, FastAPI, Pydantic v2 | typed, auto OpenAPI docs, best AI ecosystem |
| DB | SQLite for dev/tests, PostgreSQL in docker-compose (SQLAlchemy 2) | single source of truth: text, tree, links, items, history |
| Vectors | in-memory store for dev/tests, Chroma when `CHROMA_HOST` is set | simple; used only as a similarity index |
| LLM | Gemini / Groq / OpenAI-compatible / fake | `.env` switch, offline demo without keys |
| Embeddings | Gemini / fake | `.env` switch, offline demo without keys |
| Extraction | python-docx, pdfplumber, OCR stub (Docling) | OCR only when a PDF has no text layer |
| Frontend | React + Vite + TypeScript (rebuilt next) | thin UI over the REST API |
| Infra | Docker Compose | one command for the whole platform |

Provider selection lives in `app/providers/factory.py`. With no API key the app falls back to the fake
providers and flags it in `/api/v1/settings/providers` and in pipeline events.

Confidentiality: free-tier Gemini may use prompts to improve Google products; for real client data use a
paid/Azure tier or self-hosted models.

## 3. Data model (`app/domain/models.py`)

- `Project` - status, checklist, context approval flag, failure reason.
- `Document` - uploaded file version + parse stats/preview.
- `Section` - tree node: parent, number, title, text, role, lineage, `is_leaf`.
- `Link` - source -> target, kind `similarity|reference|lexical|manual`, score, reason, enabled.
- `GlossaryTerm` - actor/term extracted from glossary-like sections.
- `ContextPack` - snapshot of the rendered prompt for a section.
- `BacklogItem` - key (`EP-01`/`US-001`/`TC-001`), kind `epic|story|test`, parent, source section(s),
  body, status, confidence.
- `Question` - question per section, answer, status.
- `GenerationTrace` - exact prompt/response, attempts, duration, status.
- `RunEvent` - append-only pipeline journal used by SSE and history.
- `ReviewEvent` - review audit trail.

## 4. API (`/api/v1`, interactive docs at `/docs`)

| Method | Path | Purpose |
|---|---|---|
| POST | /projects | upload + auto prepare (parse, structure, link) |
| GET | /projects | list projects |
| GET/DELETE | /projects/{id} | read / delete a project |
| GET | /projects/{id}/document | stats, checklist, warnings, pivot preview |
| GET | /projects/{id}/sections | tree/sections |
| PATCH | /sections/{id} | change role / title |
| GET | /projects/{id}/links | list links |
| POST | /projects/{id}/links | create a manual link |
| PATCH/DELETE | /links/{id} | enable/disable / delete a link |
| GET | /sections/{id}/context | context pack + rendered prompt preview |
| POST | /projects/{id}/pipeline/prepare | re-run parse + structure + link |
| POST | /projects/{id}/pipeline/approve-context | human checkpoint 1 |
| POST | /projects/{id}/pipeline/generate | background generation (requires approval) |
| POST | /projects/{id}/pipeline/retry-failed | regenerate failed leaves |
| GET | /projects/{id}/pipeline/status | current status + progress |
| GET | /projects/{id}/events | SSE stream |
| GET | /projects/{id}/events/history | event replay |
| GET | /projects/{id}/backlog | nested epics > stories > tests + stats |
| PATCH | /items/{id} | approve / edit / reject |
| POST | /items/{id}/regenerate | regenerate one item with an instruction |
| POST | /projects/{id}/backlog/approve | human checkpoint 2 |
| GET | /projects/{id}/questions | list questions |
| PATCH | /questions/{id} | answer a question |
| GET | /projects/{id}/coverage | traceability matrix + coverage % |
| GET | /projects/{id}/export?format=xlsx\|csv\|jira\|azure | export (jira/azure -> 501) |
| POST | /projects/{id}/ask | ask the spec, returns answer + citations |
| POST | /projects/{id}/versions | spec v2 impact (501 for now) |
| GET | /settings/providers | active providers / fake flag |
| GET | /health | health check |

## 5. Repo map

```
spec2backlog/
  docker-compose.yml  .env.example  Makefile
  samples/exemple_specifications.docx
  docs/BLUEPRINT.md  docs/ARCHITECTURE.md
  backend/
    app/main.py
    app/core/{config,db,events,jobs,schema}.py
    app/domain/{models,schemas,enums}.py
    app/providers/{factory.py,llm/,embeddings/}
    app/modules/ingestion/{parsers/,pivot.py,quality.py,service.py}
    app/modules/structure/{tree.py,classifier.py,service.py}
    app/modules/knowledge/{chunker,embedder,vector_store,retriever,reranker,glossary,service}.py
    app/modules/context/{builder,budget}.py
    app/modules/generation/{prompts/,schema,generator,consolidator,quality,service}.py
    app/modules/review/service.py
    app/modules/export/{excel,csv,traceability,jira,azure_devops}.py
    app/modules/assistant/ask.py
    app/modules/versions/{diff,impact}.py
    app/modules/evaluation/{metrics,golden}.py
    app/api/v1/{projects,document,structure,context,pipeline,events,backlog,questions,export,assistant,versions,settings}.py
    tests/
  frontend/
```

## 6. Roadmap (suggested order)

1. **Ingestion quality**: scanned PDF/OCR, table -> structured rows, heading detection when styles are missing.
2. **Knowledge quality**: calibrate hybrid retrieval on the sample, annotate expected links, measure recall;
   add a real reranker.
3. **Generation quality**: richer output schema, consolidation tuning, canonical project model (actors, entities).
4. **Async jobs**: replace in-process threads with arq/RQ + progress bar, Alembic migrations, auth (EY SSO).
5. **Exports**: Jira bulk API, Azure DevOps work items; round-trip keys stored for re-sync.
6. **Evaluation**: BA-written reference backlog on the sample, score coverage + traceability + edit rate.

## 7. Known gaps (deliberate, skeleton)

No auth, generation runs in an in-process background thread, Jira/AzDO/versions/OCR/reranker/golden are stubs,
PDF headings are font-size heuristics, tables are flattened to text, long leaves are chunked for embeddings
but the prompt uses the truncated leaf text, multi-hop context is not used (direct links only).
