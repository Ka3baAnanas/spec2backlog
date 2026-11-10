from typing import Protocol


class EmbeddingClient(Protocol):
    def embed(self, texts: list[str], task: str = "document") -> list[list[float]]: ...
