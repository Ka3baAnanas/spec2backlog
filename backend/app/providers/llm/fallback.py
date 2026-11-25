"""Provider-level fallback: use the primary LLM, switch to a secondary on failure.

Unlike the in-provider fallback inside GeminiLLM (another model of the same
vendor), this wrapper lets one vendor (e.g. Ollama) fail over to another
(e.g. Gemini) and stays switched for the rest of the run.
"""

import logging

logger = logging.getLogger(__name__)


class FallbackLLM:
    def __init__(self, primary, secondary):
        self.primary = primary
        self.secondary = secondary
        self.name = getattr(primary, "name", type(primary).__name__)
        self.model = getattr(primary, "model", "")
        self.fallback_name = getattr(secondary, "name", type(secondary).__name__)
        self.fallback_model = getattr(secondary, "model", "")
        self._use_secondary = False

    def complete_json(self, system: str, user: str, schema: dict, on_event=None) -> dict:
        if self._use_secondary:
            return self.secondary.complete_json(system, user, schema, on_event=on_event)
        try:
            return self.primary.complete_json(system, user, schema, on_event=on_event)
        except Exception as exc:  # noqa: BLE001 - any provider failure must fail over
            self._use_secondary = True
            logger.warning(
                "%s failed; switching to %s: %s", self.name, self.fallback_name, exc
            )
            if on_event:
                on_event(
                    "warning",
                    f"{self.name} unavailable; switching to {self.fallback_name}",
                    {
                        "reason": "provider_failed",
                        "provider": self.name,
                        "fallback_provider": self.fallback_name,
                        "fallback_model": self.fallback_model,
                        "error": f"{type(exc).__name__}: {exc}",
                    },
                )
            return self.secondary.complete_json(system, user, schema, on_event=on_event)
