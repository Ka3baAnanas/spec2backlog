import httpx

from app.core.config import settings


class GeminiEmbedder:
    name = "gemini"
    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents"

    def __init__(self):
        self.key = settings.gemini_api_key
        self.model = settings.embedding_model

    def embed(self, texts: list[str], task: str = "document") -> list[list[float]]:
        task_type = "RETRIEVAL_DOCUMENT" if task == "document" else "RETRIEVAL_QUERY"
        body = {
            "requests": [
                {
                    "model": f"models/{self.model}",
                    "taskType": task_type,
                    "content": {"parts": [{"text": text}]},
                }
                for text in texts
            ]
        }
        r = httpx.post(
            self.URL.format(model=self.model),
            params={"key": self.key},
            json=body,
            timeout=60,
        )
        r.raise_for_status()
        return [entry["values"] for entry in r.json()["embeddings"]]
