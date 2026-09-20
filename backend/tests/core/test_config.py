import pytest
from pydantic import ValidationError

from core.config import Settings
from enums import LlmProvider


def test_settings_defaults_need_no_environment() -> None:
    settings = Settings(_env_file=None)
    assert settings.llm_provider is LlmProvider.GOOGLE
    assert settings.search_cache_ttl_seconds == 600
    assert settings.llm_api_key.get_secret_value() == ""


def test_settings_parse_provider_and_hide_the_key() -> None:
    settings = Settings(
        _env_file=None, llm_provider="openai_compatible", llm_api_key="sk-test"
    )
    assert settings.llm_provider is LlmProvider.OPENAI_COMPATIBLE
    assert "sk-test" not in repr(settings)


def test_empty_jwt_secret_is_rejected_outside_development() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(_env_file=None, env="production", jwt_secret="")


def test_short_jwt_secret_is_rejected() -> None:
    with pytest.raises(ValidationError, match="32 bytes"):
        Settings(_env_file=None, env="production", jwt_secret="too-short")


def test_empty_jwt_secret_in_development_becomes_a_random_secret() -> None:
    first = Settings(_env_file=None, env="development", jwt_secret="")
    second = Settings(_env_file=None, env="development", jwt_secret="")
    assert len(first.jwt_secret.get_secret_value()) >= 32
    assert first.jwt_secret.get_secret_value() != second.jwt_secret.get_secret_value()


def test_auth_defaults_match_the_spec() -> None:
    settings = Settings(_env_file=None, env="development")
    assert settings.access_token_minutes == 15
    assert settings.refresh_token_days == 30
    assert settings.scrypt_n == 2**17
    assert settings.admin_email == ""
    assert settings.admin_password.get_secret_value() == ""
