"""Text normalization shared by the LLM schema and the offline provider."""

import re


def _lower_first(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    return text[0].lower() + text[1:]


def normalize_goal(value: str) -> str:
    """Return a single infinitive goal: 'to <verb phrase>'."""
    text = _lower_first(value)
    text = re.sub(r"^to\s+(?:to\s+)*", "", text, flags=re.IGNORECASE)
    text = _lower_first(re.sub(r"\s+", " ", text).strip())
    return f"to {text}" if text else ""


def normalize_benefit(value: str) -> str:
    """Return a lowercase purpose clause, without a duplicate leading 'to'."""
    text = _lower_first(value)
    text = re.sub(r"^to\s+", "", text, flags=re.IGNORECASE)
    return _lower_first(re.sub(r"\s+", " ", text).strip())
