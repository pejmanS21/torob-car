from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openai import OpenAIChatModel

from core.config import Settings
from llm.model_factory import build_model


def settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_no_api_key_means_no_model() -> None:
    assert build_model(settings()) is None


def test_google_provider_builds_a_gemini_model() -> None:
    model = build_model(settings(llm_provider="google", llm_api_key="test-key"))
    assert isinstance(model, GoogleModel)
    assert model.model_name == "gemini-3.7-flash"


def test_openai_compatible_provider_uses_the_configured_base_url() -> None:
    model = build_model(
        settings(
            llm_provider="openai_compatible",
            llm_api_key="test-key",
            llm_model="openai/gpt-5-mini",
            llm_base_url="https://openrouter.ai/api/v1",
        )
    )
    assert isinstance(model, OpenAIChatModel)
    assert str(model.client.base_url).startswith("https://openrouter.ai/api/v1")
