def rerank(question: str, candidates: list[dict], top_k: int = 5) -> list[dict]:
    raise NotImplementedError(
        "Reranker is not implemented yet; hybrid retrieval order is used instead."
    )
