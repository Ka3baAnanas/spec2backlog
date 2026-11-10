"""Provider factory: an `.env` switch, with an honest offline fake fallback."""

from app.core.config import settings
from app.providers.embeddings.fake import FakeEmbedder
from app.providers.embeddings.gemini import GeminiEmbedder
from app.providers.llm.fake import FakeLLM
from app.providers.llm.gemini import GeminiLLM
from app.providers.llm.groq import GroqLLM
from app.providers.llm.openai_compat import OpenAICompatLLM


def get_llm():
    provider = (settings.llm_provider or "fake").lower()
    if provider == "fake":
        return FakeLLM()
    if provider == "gemini":
        return GeminiLLM() if settings.gemini_api_key else FakeLLM()
    if provider == "groq":
        return GroqLLM() if settings.groq_api_key else FakeLLM()
    if provider == "openai_compat":
        return OpenAICompatLLM() if settings.llm_base_url else FakeLLM()
    return FakeLLM()


def get_embedder():
    provider = (settings.embedding_provider or "fake").lower()
    if provider == "gemini":
        return GeminiEmbedder() if settings.gemini_api_key else FakeEmbedder()
    return FakeEmbedder()


def provider_info() -> dict:
    llm = get_llm()
    embedder = get_embedder()
    llm_fake = getattr(llm, "name", "") == "fake"
    embedder_fake = getattr(embedder, "name", "") == "fake"
    return {
        "llm": {
            "configured": settings.llm_provider,
            "active": getattr(llm, "name", type(llm).__name__),
            "model": settings.llm_model,
            "fake": llm_fake,
        },
        "embeddings": {
            "configured": settings.embedding_provider,
            "active": getattr(embedder, "name", type(embedder).__name__),
            "model": settings.embedding_model,
            "fake": embedder_fake,
        },
        "offline_demo": llm_fake or embedder_fake,
        "message": (
            "Fake providers active: the flow works offline and generated content is demo-only."
            if (llm_fake or embedder_fake)
            else "Real providers configured."
        ),
    }
