from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/dev.db"  # Postgres in docker-compose
    llm_provider: str = "groq"
    llm_model: str = "openai/gpt-oss-120b"
    llm_base_url: str = ""
    groq_api_key: str = ""
    embedding_provider: str = "gemini"
    embedding_model: str = "gemini-embedding-001"
    gemini_api_key: str = ""
    chroma_host: str = ""  # empty => in-memory fallback (dev/tests)
    chroma_port: int = 8000
    similar_top_k: int = 3
    similar_min_score: float = 0.55
    max_leaf_tokens: int = 1500
    demo_delay_ms: int = 0  # artificial per-leaf delay so demos show the animation


settings = Settings()
