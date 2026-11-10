"""Token budget and truncation order for the context pack."""

from app.core.config import settings


def estimate_tokens(text: str) -> int:
    return max(1, len(text or "") // 4)


def truncate_text(text: str, max_tokens: int) -> str:
    max_chars = max(0, max_tokens) * 4
    if len(text or "") <= max_chars:
        return text or ""
    return (text or "")[:max_chars].rstrip() + "\n[...truncated]"


def fit_sections(
    sections: list[dict], max_tokens: int, per_section_tokens: int | None = None
) -> tuple[list[dict], list[dict]]:
    """Keep sections in relevance order until the budget is spent.

    Returns (kept, dropped). Sections beyond the budget are dropped, and the first
    oversized section is truncated instead of dropped.
    """
    per_section_tokens = per_section_tokens or settings.max_leaf_tokens
    kept: list[dict] = []
    dropped: list[dict] = []
    used = 0
    for section in sections:
        text = truncate_text(section.get("text", ""), per_section_tokens)
        cost = estimate_tokens(text)
        if used + cost > max_tokens and kept:
            dropped.append(section)
            continue
        kept.append({**section, "text": text})
        used += cost
    return kept, dropped
