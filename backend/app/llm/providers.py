"""Swappable providers. Default = Groq (LLM) + Gemini (embeddings) for the prototype.
For REAL client data switch to azure_openai / local via env vars, no code change."""
import hashlib
import json
import math

import httpx

from app.core.config import settings


class OpenAICompatLLM:
    """Works for Groq, Azure OpenAI, vLLM, Ollama (all speak /chat/completions)."""

    def __init__(self):
        p = settings.llm_provider
        self.base = settings.llm_base_url or {"groq": "https://api.groq.com/openai/v1"}.get(p, "")
        self.key = settings.groq_api_key
        self.model = settings.llm_model

    def complete_json(self, system: str, user: str, schema: dict) -> dict:
        r = httpx.post(
            f"{self.base}/chat/completions",
            headers={"Authorization": f"Bearer {self.key}"},
            json={
                "model": self.model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "response_format": {"type": "json_object"},
                "temperature": 0.2,
            },
            timeout=120,
        )
        r.raise_for_status()
        return json.loads(r.json()["choices"][0]["message"]["content"])


class GeminiEmbedder:
    URL = "https://generativelanguage.googleapis.com/v1beta/models/{m}:batchEmbedContents"

    def embed(self, texts, task="document"):
        t = "RETRIEVAL_DOCUMENT" if task == "document" else "RETRIEVAL_QUERY"
        m = settings.embedding_model
        body = {"requests": [{"model": f"models/{m}", "taskType": t,
                              "content": {"parts": [{"text": x}]}} for x in texts]}
        r = httpx.post(self.URL.format(m=m), params={"key": settings.gemini_api_key}, json=body, timeout=60)
        r.raise_for_status()
        return [e["values"] for e in r.json()["embeddings"]]


class FakeEmbedder:
    """Deterministic hashing bag-of-words. For tests / offline demo only."""

    def embed(self, texts, task="document"):
        out = []
        for t in texts:
            v = [0.0] * 256
            for w in t.lower().split():
                v[int(hashlib.md5(w.encode()).hexdigest(), 16) % 256] += 1
            n = math.sqrt(sum(x * x for x in v)) or 1
            out.append([x / n for x in v])
        return out


class FakeLLM:
    def complete_json(self, system, user, schema):
        return {"epic": {"title": "Demo epic"}, "stories": [], "tests": [], "questions": []}


def get_llm():
    return OpenAICompatLLM() if settings.groq_api_key or settings.llm_base_url else FakeLLM()


def get_embedder():
    return GeminiEmbedder() if settings.gemini_api_key else FakeEmbedder()
