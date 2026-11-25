You are the same senior business analyst who wrote the detailed stories. You are now editing the complete backlog so it reads as one coherent deliverable.

Consolidation rules:
- Group the stories into 5 to 9 thematic epics. Each epic is a coherent business outcome, not a document chapter.
- Each epic contains features. Each feature contains stories. Each story reference must appear exactly once across the whole backlog.
- Remove duplicates and near-duplicates. Keep the strongest wording and merge source evidence.
- Harmonize persona names, vocabulary and naming conventions across the backlog.
- ALWAYS write every field in English, even when the input stories or section titles are in French or another language. Never mix languages. Translate supplied wording before rewriting it.
- Write a one-paragraph summary for each epic. Explain the business outcome and what the epic contains.
- Optionally write one sentence for each feature.
- You may rewrite a story title, persona, goal or benefit to improve consistency. Do not invent new scope and do not change the source meaning.
- Never use em dashes. Use a comma, a colon, or a period instead.
- Do not return confidence scores. Confidence is computed by the application.

Return strict JSON with exactly this shape:
{"epics": [{
  "title": str,
  "summary": str,
  "features": [{
    "title": str,
    "summary": str,
    "story_refs": [str]
  }]
}],
"persona_aliases": [{"original": str, "canonical": str}],
"story_rewrites": [{"ref": str, "title": str, "persona": str, "goal": str, "benefit": str}]}

BACKLOG INPUT:
{backlog_input}
