"""The only module that knows which LLM provider is in use (spec §8.1)."""

from pydantic_ai.models import Model
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.openai import OpenAIProvider

from core.config import Settings
from enums import LlmProvider


def build_model(settings: Settings) -> Model | None:
    """None when no API key is configured: search then runs on the rules parser."""
    api_key = settings.llm_api_key.get_secret_value()
    if not api_key:
        return None
    match settings.llm_provider:
        case LlmProvider.GOOGLE:  # development — Gemini API
            return GoogleModel(
                settings.llm_model, provider=GoogleProvider(api_key=api_key)
            )
        case LlmProvider.OPENAI_COMPATIBLE:  # production — OpenRouter or OpenAI-like
            provider = OpenAIProvider(
                base_url=settings.llm_base_url or None, api_key=api_key
            )
            return OpenAIChatModel(settings.llm_model, provider=provider)
