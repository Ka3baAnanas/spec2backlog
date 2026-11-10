from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Spec2Backlog"
    debug: bool = False

    database_url: str = "sqlite:///./data/dev.db"
    uploads_dir: str = "data/uploads"

    # LLM: gemini | groq | openai_compat | fake
    # gemini-3.5-flash-lite is a stable, free-tier text-generation model.
    llm_provider: str = "gemini"
    llm_model: str = "gemini-3.5-flash-lite"
    llm_base_url: str = ""
    groq_api_key: str = ""
    gemini_api_key: str = ""

    # Embeddings: gemini | fake
    # gemini-embedding-2 is the current free-tier multimodal embedding model.
    embedding_provider: str = "gemini"
    embedding_model: str = "gemini-embedding-2"

    # Vector store: Chroma when chroma_host is set, otherwise in-memory
    chroma_host: str = ""
    chroma_port: int = 8000

    # Retrieval knobs
    similar_top_k: int = 3
    similar_min_score: float = 0.55
    lexical_min_score: float = 0.12

    # Context / generation knobs
    max_leaf_tokens: int = 1500
    context_max_tokens: int = 6000
    demo_delay_ms: int = 0  # artificial per-leaf delay so demos show progress

    # Gemini free-tier safety: ~15 RPM by default, retry 429/5xx with backoff.
    gemini_min_interval_seconds: float = 4.0
    gemini_max_retries: int = 6
    gemini_retry_base_seconds: float = 2.0
    gemini_retry_max_seconds: float = 60.0


settings = Settings()
