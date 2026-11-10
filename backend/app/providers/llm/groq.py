from app.core.config import settings
from app.providers.llm.openai_compat import OpenAICompatLLM


class GroqLLM(OpenAICompatLLM):
    name = "groq"

    def __init__(self):
        super().__init__(
            base_url=settings.llm_base_url or "https://api.groq.com/openai/v1",
            api_key=settings.groq_api_key,
            model=settings.llm_model,
        )
