from collections.abc import Callable

from app.providers.factory import get_embedder

EventHook = Callable[[str, str, dict], None]


def embed_texts(
    texts: list[str], task: str = "document", on_event: EventHook | None = None
) -> list[list[float]]:
    if not texts:
        return []
    return get_embedder().embed(texts, task=task, on_event=on_event)
