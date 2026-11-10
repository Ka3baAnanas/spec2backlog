"""Deterministic offline LLM used for tests and demos. Content is clearly fake."""

import re

SECTION_PATH_RE = re.compile(r"SECTION PATH:\s*(.+)")
SECTION_TEXT_RE = re.compile(r"SECTION TEXT:\s*(.*)", re.DOTALL)


def _section_title(user: str) -> str:
    match = SECTION_PATH_RE.search(user)
    if not match:
        return "the section"
    path = [part.strip() for part in match.group(1).split(">") if part.strip()]
    return path[-1] if path else "the section"


def _section_text(user: str) -> str:
    match = SECTION_TEXT_RE.search(user)
    return match.group(1).strip() if match else ""


class FakeLLM:
    name = "fake"

    def complete_json(self, system: str, user: str, schema: dict) -> dict:
        title = _section_title(user)
        text = _section_text(user)
        excerpt = text.strip().splitlines()[0][:180] if text.strip() else title
        story_title = f"Handle {title}"
        return {
            "epic": {"title": f"Epic - {title}"},
            "stories": [
                {
                    "title": story_title,
                    "as_a": "business user",
                    "i_want": f"the behaviour described in {title}",
                    "so_that": "the specification is implemented as expected",
                    "acceptance_criteria": [
                        (
                            f"Given the context of {title}, when the described flow is used, "
                            f"then the expected result is observed ({excerpt})"
                        )
                    ],
                    "priority": "must",
                }
            ],
            "tests": [
                {
                    "title": f"Verify {title}",
                    "steps": [f"Open the {title} flow", "Execute the described scenario"],
                    "expected": "The behaviour matches the specification.",
                    "story_title": story_title,
                }
            ],
            "questions": [],
        }
