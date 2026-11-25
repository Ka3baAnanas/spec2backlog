# Spec2Backlog - functional specs -> validated backlog + test cases (EY Cortex AI)

Turn a client's functional specification (Word/PDF) into a validated backlog (epics, user stories,
acceptance criteria, test cases) with full traceability to the source text.

The product follows five steps, one screen per step, with two human checkpoints (context approval,
backlog approval). Every item stays traceable to its source section; details are on demand. Stubs are
honest: HTTP 501 and "Soon" in the UI, never fake results.

The source of truth for the product and architecture is [`docs/BLUEPRINT.md`](docs/BLUEPRINT.md).
See also [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Pipeline

```
uploaded -> parsed -> structured -> linked -> awaiting_context_approval
        -> generating -> generated -> in_review -> approved -> exported
        (+ failed with reason)
```

Parse, structure and link run automatically after upload (`prepare`). Generation only starts after the
human approves the context. Only sections whose role is `requirement` are generated; disabled links are
excluded from the prompt.

## Quick start

```bash
cp .env.example .env        # add OLLAMA_API_KEY and/or GEMINI_API_KEY; use LLM_PROVIDER=fake for offline demo
make up                     # Postgres + Redis + Celery worker + Chroma + FastAPI (:8000/docs) + React (:5173)
make test                   # end-to-end test on samples/exemple_specifications.docx
```

**Fake mode is explicit**: set `LLM_PROVIDER=fake` (and optionally `EMBEDDING_PROVIDER=fake`) for the
offline deterministic stub flow; content is clearly marked as demo. A configured real provider that is
unavailable never silently degrades to demo output: the run pauses, retries from saved traces, and only
publishes a backlog once generation and consolidation succeed. `/api/v1/settings/providers` reports the
active providers and whether they are fake.

## Docs

- `docs/BLUEPRINT.md` - product blueprint (source of truth)
- `docs/ARCHITECTURE.md` - architecture, data model, API, repo map, roadmap, risks
