"""Provider factory: an `.env` switch, with explicit fake providers only."""

from app.core.config import settings
from app.providers.embeddings.fake import FakeEmbedder
from app.providers.embeddings.gemini import GeminiEmbedder
from app.providers.errors import ProviderConfigurationError, ProviderError
from app.providers.llm.fake import FakeLLM
from app.providers.llm.fallback import FallbackLLM
from app.providers.llm.gemini import GeminiLLM
from app.providers.llm.groq import GroqLLM
from app.providers.llm.openai_compat import OpenAICompatLLM

# A local Ollama (no key required) is anything that is not the cloud endpoint.
OLLAMA_CLOUD_HOST = "ollama.com"


def _make_llm(provider: str):
    """Build a provider, or return None when it is not configured."""
    provider = (provider or "").lower()
    if provider == "fake":
        return FakeLLM()
    if provider == "gemini":
        return GeminiLLM() if settings.gemini_api_key else None
    if provider == "groq":
        return GroqLLM() if settings.groq_api_key else None
    if provider == "ollama":
        base = settings.ollama_base_url or "https://ollama.com/v1"
        local = OLLAMA_CLOUD_HOST not in base
        if not settings.ollama_api_key and not local:
            return None
        return OpenAICompatLLM(
            base_url=base,
            api_key=settings.ollama_api_key,
            model=settings.llm_model,
            name="ollama",
        )
    if provider == "openai_compat":
        return OpenAICompatLLM() if settings.llm_base_url else None
    return None


def get_llm():
    primary = _make_llm(settings.llm_provider)
    fallback_provider = (settings.llm_fallback_provider or "").lower()
    fallback = None
    if fallback_provider and fallback_provider != (settings.llm_provider or "").lower():
        fallback = _make_llm(fallback_provider)
    if primary is None:
        if fallback is not None:
            return fallback
        raise ProviderConfigurationError(
            f"Configured LLM provider '{settings.llm_provider}' is not available"
        )
    if fallback is None or getattr(primary, "name", "") == "fake":
        return primary
    return FallbackLLM(primary, fallback)


def get_embedder():
    provider = (settings.embedding_provider or "fake").lower()
    if provider == "gemini":
        return GeminiEmbedder() if settings.gemini_api_key else FakeEmbedder()
    return FakeEmbedder()


def provider_info() -> dict:
    llm_unavailable: str | None = None
    try:
        llm = get_llm()
    except ProviderError as exc:
        llm = None
        llm_unavailable = str(exc)
    embedder = get_embedder()
    llm_fake = getattr(llm, "name", "") == "fake"
    embedder_fake = getattr(embedder, "name", "") == "fake"
    llm_info = {
        "configured": settings.llm_provider,
        "active": "unavailable" if llm is None else getattr(llm, "name", type(llm).__name__),
        "model": settings.llm_model,
        "fake": llm_fake,
    }
    if llm_unavailable:
        llm_info["error"] = llm_unavailable
    if getattr(llm, "fallback_name", None):
        llm_info["fallback"] = {
            "provider": llm.fallback_name,
            "model": getattr(llm, "fallback_model", ""),
        }
    return {
        "llm": llm_info,
        "embeddings": {
            "configured": settings.embedding_provider,
            "active": getattr(embedder, "name", type(embedder).__name__),
            "model": settings.embedding_model,
            "fake": embedder_fake,
        },
        "offline_demo": llm_fake or embedder_fake,
        "message": (
            llm_unavailable
            if llm_unavailable
            else (
                "Fake providers active: the flow works offline and generated content is demo-only."
                if (llm_fake or embedder_fake)
                else "Real providers configured."
            )
        ),
    }
