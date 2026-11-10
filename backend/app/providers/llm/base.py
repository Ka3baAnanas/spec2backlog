from typing import Protocol


class LLMClient(Protocol):
    def complete_json(self, system: str, user: str, schema: dict) -> dict: ...


class EmbeddingClient(Protocol):
    def embed(self, texts: list[str], task: str = "document") -> list[list[float]]: ...
