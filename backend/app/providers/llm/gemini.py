import json

from app.core.config import settings
from app.providers.errors import ProviderUnavailableError
from app.providers.gemini_http import post_with_retry


class GeminiLLM:
    name = "gemini"
    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self):
        self.key = settings.gemini_api_key
        primary = settings.llm_model or ""
        self.model = primary if primary.startswith("gemini") else (
            settings.gemini_fallback_model or "gemini-3.5-flash"
        )
        self.fallback_model = settings.gemini_fallback_model or "gemini-3.5-flash"
        self._use_fallback = False

    def _complete_with_model(
        self, model: str, system: str, user: str, on_event=None
    ) -> dict:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
            },
        }
        response = post_with_retry(
            f"gemini-llm:{model}",
            self.URL.format(model=model),
            params={"key": self.key},
            json=body,
            timeout=180,
            on_event=on_event,
            retry_503_exact=True,
        )
        text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)

    def complete_json(self, system: str, user: str, schema: dict, on_event=None) -> dict:
        models = [self.fallback_model] if self._use_fallback else [self.model]
        if not self._use_fallback and self.fallback_model not in models:
            models.append(self.fallback_model)

        last_error: Exception | None = None
        for index, model in enumerate(models):
            try:
                return self._complete_with_model(model, system, user, on_event=on_event)
            except json.JSONDecodeError:
                raise
            except Exception as exc:
                last_error = exc
                if index < len(models) - 1:
                    self._use_fallback = True
                    if on_event:
                        on_event(
                            "warning",
                            f"{model} unavailable; switching to {self.fallback_model}",
                            {
                                "reason": "primary_model_failed",
                                "model": model,
                                "fallback_model": self.fallback_model,
                                "error": f"{type(exc).__name__}: {exc}",
                            },
                        )
                    continue
                raise
        if isinstance(last_error, ProviderUnavailableError):
            raise last_error
        raise ProviderUnavailableError("Gemini unavailable") from last_error
