"""Application settings — the ONLY module allowed to read the environment."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from enums import LlmProvider


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    env: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://app:app@db:5432/app"
    test_database_url: str = "postgresql+asyncpg://app:app@127.0.0.1:54329/app_test"
    redis_url: str = "redis://redis:6379/0"
    search_cache_ttl_seconds: int = 600
    intent_cache_ttl_seconds: int = 86_400
    llm_provider: LlmProvider = LlmProvider.GOOGLE
    llm_model: str = "gemini-3.7-flash"
    llm_api_key: SecretStr = SecretStr("")
    llm_base_url: str | None = None
    llm_timeout_seconds: float = 4.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
