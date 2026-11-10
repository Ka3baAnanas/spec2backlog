# Spec2Backlog — functional specs → backlog + test cases (EY Cortex AI)

Upload a functional specification (Word/PDF) → the system builds a tree, links related sections (meaning graph),
generates epics / user stories / acceptance criteria / tests with an LLM, a Business Analyst validates, and the
result is exported (Excel now; Jira / Azure DevOps next) with traceability back to the source section.

## Quick start
```bash
cp .env.example .env        # add GROQ_API_KEY and GEMINI_API_KEY (or leave empty = offline fake mode)
make up                     # Postgres + Chroma + FastAPI (:8000/docs) + React (:5173)
make test                   # end-to-end test on samples/exemple_specifications.docx
```
Without API keys the app runs in **fake mode** (hash embeddings + stub LLM): the whole flow works, content is dummy.

## Docs
- `docs/ARCHITECTURE.md` — workflow, stack choices, data model, API, repo map, roadmap, risks
