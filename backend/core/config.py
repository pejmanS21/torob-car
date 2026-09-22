"""Application settings — the ONLY module allowed to read the environment."""

import logging
import secrets
from functools import lru_cache
from typing import Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from enums import LlmProvider

logger = logging.getLogger(__name__)

DEVELOPMENT_ENV = "development"
MIN_JWT_SECRET_BYTES = 32  # RFC 7518 §3.2: an HS256 key is at least the hash size
_GENERATED_SECRET_BYTES = 48


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    env: str = DEVELOPMENT_ENV
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
    assistant_timeout_seconds: float = 20.0  # tool calls need two round trips
    anonymous_chat_daily_limit: int = Field(default=3, ge=1)
    jwt_secret: SecretStr = SecretStr("")
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    scrypt_n: int = 2**17
    admin_email: str = ""
    admin_password: SecretStr = SecretStr("")
    admin_session_minutes: int = 60
    admin_reauth_minutes: int = 5

    @property
    def is_development(self) -> bool:
        return self.env == DEVELOPMENT_ENV

    @model_validator(mode="after")
    def _resolve_jwt_secret(self) -> Self:
        secret = self.jwt_secret.get_secret_value()
        if secret:
            if len(secret.encode()) < MIN_JWT_SECRET_BYTES:
                raise ValueError(
                    f"JWT_SECRET must be at least {MIN_JWT_SECRET_BYTES} bytes"
                )
            return self
        if not self.is_development:
            raise ValueError("JWT_SECRET must be set outside development")
        logger.warning("JWT_SECRET is empty: using a random secret for this process")
        self.jwt_secret = SecretStr(secrets.token_urlsafe(_GENERATED_SECRET_BYTES))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
