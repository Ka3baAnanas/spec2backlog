import json

import httpx

from app.core.config import settings


class OpenAICompatLLM:
    """Works for Groq, Azure OpenAI, vLLM, Ollama (all speak /chat/completions)."""

    name = "openai_compat"

    def __init__(self, base_url: str | None = None, api_key: str | None = None,
                 model: str | None = None):
        self.base = (base_url if base_url is not None else settings.llm_base_url).rstrip("/")
        self.key = api_key if api_key is not None else settings.groq_api_key
        self.model = model or settings.llm_model

    def complete_json(self, system: str, user: str, schema: dict) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["Authorization"] = f"Bearer {self.key}"
        r = httpx.post(
            f"{self.base}/chat/completions",
            headers=headers,
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.2,
            },
            timeout=120,
        )
        r.raise_for_status()
        return json.loads(r.json()["choices"][0]["message"]["content"])
