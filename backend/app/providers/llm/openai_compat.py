import json
import time

import httpx

from app.core.config import settings
from app.providers.errors import ProviderUnavailableError

_RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


def _retry_delay(attempt: int, response: httpx.Response | None = None) -> float:
    maximum = max(0.0, settings.llm_retry_max_seconds)
    base = max(0.0, settings.llm_retry_base_seconds)
    if response is not None:
        header = response.headers.get("retry-after")
        if header:
            try:
                return min(maximum, max(0.0, float(header)))
            except ValueError:
                pass
    return min(maximum, base * (2**attempt))


class OpenAICompatLLM:
    """Works for Groq, Azure OpenAI, vLLM, Ollama (all speak /chat/completions)."""

    name = "openai_compat"

    def __init__(self, base_url: str | None = None, api_key: str | None = None,
                 model: str | None = None, name: str | None = None,
                 timeout: float | None = None):
        self.base = (base_url if base_url is not None else settings.llm_base_url).rstrip("/")
        self.key = api_key if api_key is not None else settings.groq_api_key
        self.model = model or settings.llm_model
        if name:
            self.name = name
        self.timeout = timeout if timeout is not None else settings.llm_timeout_seconds

    def complete_json(
        self, system: str, user: str, schema: dict, on_event=None
    ) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["Authorization"] = f"Bearer {self.key}"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
        max_retries = max(0, settings.llm_max_retries)
        for attempt in range(max_retries + 1):
            try:
                r = httpx.post(
                    f"{self.base}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )
                if r.status_code in _RETRYABLE_STATUS and attempt < max_retries:
                    delay = _retry_delay(attempt, r)
                    if on_event:
                        on_event(
                            "warning",
                            f"{self.name} returned {r.status_code}; retrying in {delay:.1f}s",
                            {
                                "provider": self.name,
                                "status": r.status_code,
                                "attempt": attempt + 1,
                                "retry_in_seconds": round(delay, 2),
                            },
                        )
                    time.sleep(delay)
                    continue
                if r.status_code in _RETRYABLE_STATUS:
                    raise ProviderUnavailableError(
                        f"{self.name} returned {r.status_code}", status_code=r.status_code
                    )
                r.raise_for_status()
                return json.loads(r.json()["choices"][0]["message"]["content"])
            except httpx.RequestError as exc:
                if attempt >= max_retries:
                    raise ProviderUnavailableError(
                        f"{self.name} network error: {type(exc).__name__}: {exc}"
                    ) from exc
                delay = _retry_delay(attempt)
                if on_event:
                    on_event(
                        "warning",
                        f"{self.name} network error; retrying in {delay:.1f}s",
                        {
                            "provider": self.name,
                            "error": f"{type(exc).__name__}: {exc}",
                            "attempt": attempt + 1,
                            "retry_in_seconds": round(delay, 2),
                        },
                    )
                time.sleep(delay)
        raise RuntimeError("unreachable")
