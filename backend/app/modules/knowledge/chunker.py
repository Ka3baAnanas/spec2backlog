"""Split long leaves into embeddings-sized chunks."""

import re

from app.core.config import settings

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_PARAGRAPH_RE = re.compile(r"\n\s*\n")


def estimate_tokens(text: str) -> int:
    """Cheap, provider-independent token estimate (4 chars ~= 1 token)."""
    return max(1, len(text or "") // 4)


def chunk_text(text: str, max_tokens: int | None = None) -> list[str]:
    max_tokens = max_tokens or settings.max_leaf_tokens
    max_chars = max_tokens * 4
    text = (text or "").strip()
    if len(text) <= max_chars:
        return [text] if text else []

    chunks: list[str] = []
    current = ""
    for paragraph in _PARAGRAPH_RE.split(text):
        pieces = [paragraph] if len(paragraph) <= max_chars else _SENTENCE_RE.split(paragraph)
        for piece in pieces:
            piece = piece.strip()
            if not piece:
                continue
            candidate = f"{current}\n{piece}".strip() if current else piece
            if len(candidate) > max_chars and current:
                chunks.append(current)
                current = piece
            else:
                current = candidate
    if current:
        chunks.append(current)
    return chunks
