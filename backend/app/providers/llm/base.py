from collections.abc import Callable
from typing import Protocol

EventHook = Callable[[str, str, dict], None]


class LLMClient(Protocol):
    def complete_json(
        self, system: str, user: str, schema: dict, on_event: EventHook | None = None
    ) -> dict: ...


class EmbeddingClient(Protocol):
    def embed(
        self, texts: list[str], task: str = "document", on_event: EventHook | None = None
    ) -> list[list[float]]: ...
