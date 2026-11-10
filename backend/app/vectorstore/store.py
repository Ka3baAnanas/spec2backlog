"""Vector index. Chroma server in docker; tiny in-memory cosine index fallback for dev/tests."""
import math

from app.core.config import settings


def _cos(a, b):
    return sum(x * y for x, y in zip(a, b)) / ((math.sqrt(sum(x * x for x in a)) or 1) * (math.sqrt(sum(y * y for y in b)) or 1))


class MemoryStore:
    def __init__(self):
        self.data: dict[str, dict[str, list[float]]] = {}

    def upsert(self, project_id, ids, vectors):
        self.data.setdefault(project_id, {}).update(dict(zip(ids, vectors)))

    def neighbours(self, project_id, vec, k, exclude=None):
        items = [(i, _cos(vec, v)) for i, v in self.data.get(project_id, {}).items() if i != exclude]
        return sorted(items, key=lambda x: -x[1])[:k]


class ChromaStore:
    def __init__(self):
        import chromadb
        self.client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)

    def _col(self, pid):
        return self.client.get_or_create_collection(f"proj_{pid}", metadata={"hnsw:space": "cosine"})

    def upsert(self, project_id, ids, vectors):
        self._col(project_id).upsert(ids=ids, embeddings=vectors)

    def neighbours(self, project_id, vec, k, exclude=None):
        r = self._col(project_id).query(query_embeddings=[vec], n_results=k + 1)
        pairs = [(i, 1 - d) for i, d in zip(r["ids"][0], r["distances"][0]) if i != exclude]
        return pairs[:k]


_store = None


def get_store():
    global _store
    if _store is None:
        _store = ChromaStore() if settings.chroma_host else MemoryStore()
    return _store
