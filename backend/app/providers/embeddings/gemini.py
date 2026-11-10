from app.core.config import settings
from app.providers.gemini_http import post_with_retry

# gemini-embedding-2 uses task instructions in the text and ignores taskType.
# gemini-embedding-001 uses the taskType field.
EMBEDDING_2_PREFIX = "gemini-embedding-2"


class GeminiEmbedder:
    name = "gemini"
    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents"

    def __init__(self):
        self.key = settings.gemini_api_key
        self.model = settings.embedding_model or "gemini-embedding-2"

    def _request(self, text: str, task: str) -> dict:
        if self.model.startswith(EMBEDDING_2_PREFIX):
            if task == "query":
                formatted = f"task: search result | query: {text}"
            else:
                formatted = f"title: none | text: {text}"
            return {
                "model": f"models/{self.model}",
                "content": {"parts": [{"text": formatted}]},
            }
        task_type = "RETRIEVAL_DOCUMENT" if task == "document" else "RETRIEVAL_QUERY"
        return {
            "model": f"models/{self.model}",
            "taskType": task_type,
            "content": {"parts": [{"text": text}]},
        }

    def embed(self, texts: list[str], task: str = "document", on_event=None) -> list[list[float]]:
        body = {"requests": [self._request(text, task) for text in texts]}
        response = post_with_retry(
            f"gemini-embeddings:{self.model}",
            self.URL.format(model=self.model),
            params={"key": self.key},
            json=body,
            timeout=120,
            on_event=on_event,
        )
        return [entry["values"] for entry in response.json()["embeddings"]]
