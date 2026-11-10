# Architecture

## 1. Workflow (end to end)
```
Upload .docx/.pdf
  1 INGESTION   extract text + headings + tables  -> PIVOT format (+ completeness checklist, OCR only if scanned)
  2 TREE        headings = nodes, text under the last heading = leaf          (services/tree)
  3 GRAPH       embeddings -> top-k neighbours + explicit refs ("voir §4.1")   (services/graph)
  4 GENERATION  1 LLM call per leaf: lineage + text + neighbours + global ctx  (services/generation)
                -> epic, stories, Given/When/Then, tests, QUESTIONS for gaps
  5 VALIDATION  BA approves / edits / rejects; every change logged             (api/routes + validation_events)
  6 EXPORT      Excel (done) -> Jira / Azure DevOps (stubs), each item linked to its source section
```
Project status: `created → ingested → graph_built → generated → validated → exported`.

## 2. Stack and why
| Layer | Choice | Why |
|---|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2 | typed, auto OpenAPI docs, best AI ecosystem |
| DB | PostgreSQL + SQLAlchemy 2 (+Alembic) | single source of truth: text, tree, edges, items, history |
| Vectors | ChromaDB (swap: pgvector) | simple; used only as a similarity index |
| LLM | gpt-oss-120b on Groq (swap: Azure OpenAI / vLLM) | fast, open-weight so it can be self-hosted |
| Embeddings | gemini-embedding-001 (swap: BGE-M3 / Qwen3-Embedding) | strong multilingual FR/EN |
| Extraction | python-docx, pdfplumber, Docling (OCR, optional) | OCR only when a PDF has no text layer |
| Frontend | React + Vite + TypeScript + TanStack Query | thin UI over the REST API |
| Infra | Docker Compose | one command for the whole platform |

**Provider abstraction** (`app/llm/providers.py`): changing LLM/embeddings is an `.env` change.
Confidentiality: free-tier Gemini may use prompts to improve Google products; for real client data use a paid/Azure
tier or self-hosted models (gpt-oss-120b, BGE-M3 are open).

## 3. Data model (`app/models`)
`projects` · `nodes` (tree: parent_id, lineage, is_leaf, is_global; id = text_id) · `edges` (leaf↔leaf, kind
similarity|reference, score) · `backlog_items` (epic/story/test, source_node_id = traceability, questions) ·
`validation_events` (before/after audit trail). Vectors live in Chroma under the same node id.

## 4. API (`/api/v1`, interactive docs at `/docs`)
| Method | Path | Purpose |
|---|---|---|
| POST | /projects/upload | file → pivot → tree (+checklist) |
| GET | /projects, /projects/{id}/tree | list projects, read the tree |
| POST/GET | /projects/{id}/graph | build / read the meaning graph |
| POST | /projects/{id}/generate | generate backlog for all leaves |
| GET | /projects/{id}/items?status= | list items |
| PATCH | /items/{id} | approve / edit / reject (logged) |
| GET | /projects/{id}/export.xlsx | export validated items |

## 5. Repo map
```
spec2backlog/
├─ docker-compose.yml  .env.example  Makefile
├─ samples/exemple_specifications.docx        tutor's example (test fixture)
├─ docs/ARCHITECTURE.md
├─ backend/
│  ├─ app/main.py                              FastAPI app
│  ├─ app/core/{config,db}.py                  settings, DB session
│  ├─ app/models/                              SQLAlchemy tables
│  ├─ app/schemas/                             Pydantic I/O
│  ├─ app/api/routes.py                        endpoints (split per resource when it grows)
│  ├─ app/services/ingestion/                  pivot, docx/pdf extractors, checklist
│  ├─ app/services/tree/builder.py             tree + DFS
│  ├─ app/services/graph/builder.py            embeddings, neighbours, references
│  ├─ app/services/generation/{prompt,runner}  prompt + per-leaf generation
│  ├─ app/services/export/{excel,jira,azure_devops}.py
│  ├─ app/llm/{base,providers}.py              swappable LLM / embedder (+ fakes)
│  ├─ app/vectorstore/store.py                 Chroma / in-memory
│  └─ tests/test_pipeline.py                   end-to-end test
└─ frontend/src/{api,pages}                    Projects, Project (tree + actions), Review
```

## 6. Roadmap (suggested order)
1. **Ingestion quality**: scanned PDF/OCR, table → structured rows, heading detection when styles are missing.
2. **Graph quality**: calibrate top-k / threshold on the sample, annotate expected links, measure recall.
3. **Generation quality**: JSON schema validation + retry, dedupe/merge stage, canonical project model (actors, entities).
4. **Async jobs** (arq/RQ + progress bar), Alembic migrations, auth (EY SSO), per-project roles.
5. **Exports**: Jira bulk API, Azure DevOps work items; round-trip keys stored for re-sync.
6. **Evaluation**: BA-written reference backlog on the sample, score coverage + traceability + edit rate.

## 7. Known gaps (deliberate, skeleton)
No auth, generation is synchronous, Jira/AzDO are stubs, PDF headings are font-size heuristics, tables are flattened
to text, long leaves are truncated (not chunked), multi-hop context not used (direct neighbours only).
