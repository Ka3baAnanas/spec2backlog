"""Vector index. Chroma server in docker; tiny in-memory cosine index fallback for dev/tests."""

import logging
import math

from app.core.config import settings


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b)) / (
        (math.sqrt(sum(x * x for x in a)) or 1)
        * (math.sqrt(sum(y * y for y in b)) or 1)
    )


class MemoryStore:
    def __init__(self):
        self.data: dict[str, dict[str, list[float]]] = {}

    def upsert(self, project_id: str, ids: list[str], vectors: list[list[float]]) -> None:
        self.data.setdefault(project_id, {}).update(dict(zip(ids, vectors)))

    def delete_project(self, project_id: str) -> None:
        self.data.pop(project_id, None)

    def neighbours(
        self, project_id: str, vector: list[float], k: int, exclude: str | None = None
    ) -> list[tuple[str, float]]:
        items = [
            (item_id, _cosine(vector, stored))
            for item_id, stored in self.data.get(project_id, {}).items()
            if item_id != exclude
        ]
        return sorted(items, key=lambda pair: -pair[1])[:k]


class ChromaStore:
    def __init__(self):
        import chromadb

        self.client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)

    def _collection(self, project_id: str):
        return self.client.get_or_create_collection(
            f"proj_{project_id}", metadata={"hnsw:space": "cosine"}
        )

    def upsert(self, project_id: str, ids: list[str], vectors: list[list[float]]) -> None:
        self._collection(project_id).upsert(ids=ids, embeddings=vectors)

    def delete_project(self, project_id: str) -> None:
        try:
            self.client.delete_collection(f"proj_{project_id}")
        except Exception as exc:  # noqa: BLE001 - missing collection is not an error
            logger.debug("Chroma collection delete skipped: %s", exc)

    def neighbours(
        self, project_id: str, vector: list[float], k: int, exclude: str | None = None
    ) -> list[tuple[str, float]]:
        result = self._collection(project_id).query(query_embeddings=[vector], n_results=k + 1)
        pairs = [
            (item_id, 1 - distance)
            for item_id, distance in zip(result["ids"][0], result["distances"][0])
            if item_id != exclude
        ]
        return pairs[:k]


logger = logging.getLogger(__name__)

_store = None


def get_store():
    global _store
    if _store is None:
        _store = ChromaStore() if settings.chroma_host else MemoryStore()
    return _store
