import json

from app.core.config import settings
from app.providers.gemini_http import post_with_retry


class GeminiLLM:
    name = "gemini"
    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self):
        self.key = settings.gemini_api_key
        self.model = settings.llm_model or "gemini-3.5-flash-lite"

    def complete_json(self, system: str, user: str, schema: dict, on_event=None) -> dict:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
            },
        }
        response = post_with_retry(
            f"gemini-llm:{self.model}",
            self.URL.format(model=self.model),
            params={"key": self.key},
            json=body,
            timeout=180,
            on_event=on_event,
        )
        text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)
