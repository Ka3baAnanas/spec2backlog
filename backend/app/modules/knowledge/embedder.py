from app.providers.factory import get_embedder


def embed_texts(texts: list[str], task: str = "document") -> list[list[float]]:
    if not texts:
        return []
    return get_embedder().embed(texts, task=task)
