SYSTEM = """You are a senior business analyst. Transform ONE functional-specification section into backlog items.
Rules:
- Use ONLY the provided text. Never invent requirements.
- If something is ambiguous or missing, add it to "questions" (for the client) instead of guessing.
- Every story needs Given/When/Then acceptance criteria; every story needs at least one test.
- Reuse the vocabulary of the GLOBAL CONTEXT. Answer in the language of the specification.
Return JSON: {"epic":{"title":str},"stories":[{"title":str,"as_a":str,"i_want":str,"so_that":str,
"acceptance_criteria":[str],"priority":"must|should|could"}],"tests":[{"title":str,"steps":[str],
"expected":str,"story_title":str}],"questions":[str]}"""


def build_user_prompt(lineage, text, neighbours, global_ctx) -> str:
    n = "\n\n".join(f"[{t['number']} {t['title']}]\n{t['text']}" for t in neighbours) or "(none)"
    g = "\n\n".join(f"[{t['title']}]\n{t['text']}" for t in global_ctx) or "(none)"
    return (f"GLOBAL CONTEXT:\n{g}\n\nRELATED SECTIONS:\n{n}\n\n"
            f"SECTION PATH: {' > '.join(lineage)}\nSECTION TEXT:\n{text}")
