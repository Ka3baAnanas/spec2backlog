from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Spec2Backlog"
    debug: bool = False

    database_url: str = "sqlite:///./data/dev.db"
    uploads_dir: str = "data/uploads"

    # LLM: ollama | gemini | groq | openai_compat | fake
    # gemini-3.5-flash-lite is a stable, free-tier text-generation model.
    llm_provider: str = "gemini"
    llm_model: str = "gemini-3.5-flash-lite"
    gemini_fallback_model: str = "gemini-3.5-flash"
    llm_fallback_provider: str = ""  # provider-level fallback, e.g. gemini
    llm_base_url: str = ""
    llm_timeout_seconds: float = 300.0
    llm_max_retries: int = 3
    llm_retry_base_seconds: float = 1.0
    llm_retry_max_seconds: float = 8.0
    groq_api_key: str = ""
    gemini_api_key: str = ""

    # Ollama (cloud: https://ollama.com/v1, local: http://host.docker.internal:11434/v1)
    ollama_api_key: str = ""
    ollama_base_url: str = "https://ollama.com/v1"

    # Background jobs: celery | in-process
    use_celery: bool = True
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"
    celery_task_max_retries: int = 3
    celery_retry_backoff_seconds: float = 5.0
    celery_retry_max_backoff_seconds: float = 300.0
    celery_queue: str = "generation"

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
    graph_max_links_per_node: int = 8
    graph_min_link_score: float = 0.45

    # Context / generation knobs
    max_leaf_tokens: int = 1500
    context_max_tokens: int = 6000
    demo_delay_ms: int = 0  # artificial per-leaf delay so demos show progress

    # Gemini free-tier safety: ~15 RPM by default, retry 429/5xx with backoff.
    gemini_min_interval_seconds: float = 4.0
    gemini_max_retries: int = 5
    gemini_retry_base_seconds: float = 2.0
    gemini_retry_max_seconds: float = 32.0


settings = Settings()
