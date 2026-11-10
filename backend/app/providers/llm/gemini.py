import json

import httpx

from app.core.config import settings


class GeminiLLM:
    name = "gemini"
    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self):
        self.key = settings.gemini_api_key
        self.model = settings.llm_model or "gemini-2.0-flash"

    def complete_json(self, system: str, user: str, schema: dict) -> dict:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
            },
        }
        r = httpx.post(
            self.URL.format(model=self.model),
            params={"key": self.key},
            json=body,
            timeout=120,
        )
        r.raise_for_status()
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)
