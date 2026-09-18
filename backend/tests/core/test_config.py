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
