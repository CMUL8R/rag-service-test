from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment or defaults."""

    # LLM Settings
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    llm_provider: str = "anthropic"
    max_tokens: int = 750
    temperature: float = 0.1

    # Database (uses SQLite by default for easy local dev/tests)
    database_url: str = "sqlite:///./rag.db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl: int = 3600

    # Vector DB / embeddings
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "documents"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    chunk_size: int = 600
    chunk_overlap: int = 100

    # Application
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


@lru_cache
def get_settings() -> "Settings":
    """Late-bind settings so tests can override env vars."""
    return Settings()


settings = get_settings()
