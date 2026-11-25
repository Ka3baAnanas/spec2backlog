PRODUCT: turn a client's functional specification (Word/PDF) into a validated backlog (epics, user stories, acceptance criteria, test cases) with full traceability to the source text.
PRINCIPLES: 5 steps, one screen per step, one primary action per screen; 2 human checkpoints (context approval, backlog approval); every item traceable to its source section; details on demand, never on the main view; stubs are honest (HTTP 501 + "Soon" in UI), never fake results.

PIPELINE STATE: uploaded -> parsed -> structured -> linked -> awaiting_context_approval -> generating -> generated -> in_review -> approved -> exported (+ failed with reason).
Steps 1-3 (parse, structure, link) run automatically after upload ("prepare"), then wait for the human.

BACKEND LAYOUT (backend/app):
 main.py
 core/        config.py, db.py, events.py (run events + SSE), jobs.py (background runner), schema guard
 domain/      models.py, schemas.py, enums.py
 providers/   llm/{base,gemini,groq,openai_compat,ollama(via openai_compat),fallback,fake}.py ; embeddings/{base,gemini,fake}.py ; factory.py
 modules/
   ingestion/   parsers/{docx,pdf,ocr(stub)}.py, pivot.py, quality.py (expected-sections checklist, warnings), service.py
   structure/   tree.py (pivot -> tree, lineage, DFS), classifier.py (role per section: requirement|context|glossary|front_matter|ignored; heuristic now, LLM later), service.py
   knowledge/   chunker.py (split long leaves), embedder.py, vector_store.py (memory|chroma), retriever.py (hybrid: vector similarity + explicit references like "voir §4.1" + lexical keyword overlap; returns reason + score per link), reranker.py (stub), glossary.py (actors/terms extraction; heuristic now), service.py
   context/     builder.py (context pack per section: lineage, text, linked sections, global context, glossary; renders the exact prompt), budget.py (token budget, truncation order)
   generation/  prompts/ (versioned .md templates), schema.py (pydantic output schema), generator.py (one call per requirement leaf, JSON validation + 1 retry, trace saved), consolidator.py (dedupe/merge similar stories across leaves, assign keys EP-01 / US-001 / TC-001), quality.py (INVEST-style checks, each story has criteria + >=1 test, confidence score), service.py
   review/      service.py (approve/edit/reject, audit trail, regenerate one item with a human instruction)
   export/      excel.py, csv.py, traceability.py (matrix section -> stories -> tests, coverage %), jira.py (stub), azure_devops.py (stub)
   assistant/   ask.py ("Ask the spec": RAG question answering with citations to sections; simple version now)
   versions/    diff.py, impact.py (stub: upload spec v2 -> changed sections -> impacted backlog items)
   evaluation/  metrics.py (coverage, acceptance rate, edit rate, time per run), golden.py (stub)
 api/v1/      projects.py, document.py, structure.py, context.py, pipeline.py, events.py, backlog.py, questions.py, export.py, assistant.py, versions.py, settings.py

DATA MODEL: Project, Document(version), Section(tree node: parent, number, title, text, role, lineage, is_leaf), Link(source, target, kind similarity|reference|lexical|manual, score, reason, enabled), GlossaryTerm, ContextPack(snapshot per section), BacklogItem(key, kind epic|story|test, parent, source_section, body, status, confidence), Question(section, text, answer, status), GenerationTrace, RunEvent, ReviewEvent.

API (/api/v1):
 POST /projects (upload + auto prepare) | GET /projects | GET/DELETE /projects/{id}
 GET /projects/{id}/document (stats, checklist, warnings, pivot preview)
 GET /projects/{id}/sections | PATCH /sections/{id} (role, title)
 GET /projects/{id}/links | POST /projects/{id}/links (manual) | PATCH/DELETE /links/{id} (enable/disable)
 GET /sections/{id}/context (context pack + rendered prompt preview)
 POST /projects/{id}/pipeline/prepare | /approve-context | /generate | /retry-failed ; GET /projects/{id}/pipeline/status
 GET /projects/{id}/events (SSE) | GET /projects/{id}/events/history
 GET /projects/{id}/backlog (nested epics > stories > tests + stats) | PATCH /items/{id} | POST /items/{id}/regenerate {instruction} | POST /projects/{id}/backlog/approve
 GET /projects/{id}/questions | PATCH /questions/{id}
 GET /projects/{id}/coverage (traceability matrix)
 GET /projects/{id}/export?format=xlsx|csv|jira|azure (jira/azure -> 501)
 POST /projects/{id}/ask {question} -> {answer, citations[]}
 POST /projects/{id}/versions -> 501 for now
 GET /settings/providers | GET /health

PROVIDERS (.env): LLM_PROVIDER=ollama|gemini|groq|openai_compat|fake ; LLM_FALLBACK_PROVIDER (optional provider-level failover, e.g. gemini) ; OLLAMA_API_KEY + OLLAMA_BASE_URL (cloud https://ollama.com/v1 or local) ; GEMINI_API_KEY ; GROQ_API_KEY ; model names configurable (LLM_MODEL, GEMINI_FALLBACK_MODEL, EMBEDDING_MODEL). EMBEDDING_PROVIDER=gemini|fake (Ollama cloud has no embeddings endpoint). Fake content is only produced when fake is explicitly configured; a configured real provider that is unavailable raises ProviderUnavailableError/ProviderConfigurationError, is reported in /settings/providers and events, and never silently degrades to demo output.

RETRY/RECOVERY: Gemini HTTP retries 429/5xx with backoff (GEMINI_* knobs) ; OpenAI-compatible providers retry 408/429/5xx and network errors with backoff (LLM_MAX_RETRIES, LLM_RETRY_BASE_SECONDS, LLM_RETRY_MAX_SECONDS) ; generator retries each leaf once ; FallbackLLM switches to the secondary provider once per run ; retryable provider failures mark the run retry_pending, wait with exponential backoff, and resume from saved traces (completed leaves are reused, failed leaves regenerated, consolidation rerun) ; failed/partial runs never publish a backlog ; /retry-failed resumes from saved traces ; /recover and startup recovery resume interrupted runs.

WORKERS: Celery with Redis broker/result backend runs generation.generate_project on the "generation" queue. Tasks retry infrastructure errors (OperationalError/InterfaceError) and retryable provider failures with exponential backoff (CELERY_RETRY_BACKOFF_SECONDS, CELERY_RETRY_MAX_BACKOFF_SECONDS) up to CELERY_TASK_MAX_RETRIES, always resuming from completed traces. USE_CELERY=false keeps the in-process thread runner for tests and local debugging. Event SSE reads RunEvent rows from PostgreSQL, so worker progress appears in the API without shared memory.

FRONTEND (see later prompt): Home (drop + projects) ; Project with tabs Pipeline | Backlog | Questions | History | Ask (beta). Pipeline = 5-step wizard: Document, Structure, Context, Generation, Backlog.
