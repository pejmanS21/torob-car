import asyncio

import pytest
from pydantic_ai import Agent, ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

from enums import ParsedBy
from errors import InvalidSearchError
from llm.intent_agent import build_instructions, build_intent_agent
from schemas.search import SearchIntent
from services.query_parser import QueryParser
from tests.support import DictCache

MILLION = 1_000_000
LLM_OUTPUT = {"cities": ["تهران"], "price_max": 800 * MILLION}


class StubCities:
    async def list_names(self) -> list[str]:
        return ["تهران", "کرج"]


def make_parser(
    agent: Agent | None, cache: DictCache, timeout: float = 1.0
) -> QueryParser:
    return QueryParser(agent, StubCities(), cache, timeout, cache_ttl_seconds=60)


def agent_returning(output: dict) -> Agent:
    return build_intent_agent(TestModel(custom_output_args=output))


async def test_llm_result_is_used_and_cached() -> None:
    cache = DictCache()
    parser = make_parser(agent_returning(LLM_OUTPUT), cache)
    first = await parser.parse("۲۰۶ زیر ۸۰۰ تهران")
    assert first.parsed_by is ParsedBy.LLM
    assert first.intent.price_max == 800 * MILLION
    offline = make_parser(None, cache)  # same cache, no LLM at all
    second = await offline.parse("  ۲۰۶ زیر ۸۰۰   تهران ")  # normalised → same key
    assert second.parsed_by is ParsedBy.LLM and second.intent == first.intent


async def test_without_an_agent_the_rules_parser_answers() -> None:
    parsed = await make_parser(None, DictCache()).parse("۲۰۶ زیر ۸۰۰ میلیون کرج")
    assert parsed.parsed_by is ParsedBy.RULES
    assert parsed.intent.cities == ["کرج"]


async def test_rules_parser_rejects_an_impossible_year_as_invalid_search() -> None:
    with pytest.raises(InvalidSearchError):
        await make_parser(None, DictCache()).parse("مدل 1450")


async def test_invalid_llm_output_falls_back_to_rules_and_is_not_cached() -> None:
    def always_invalid(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        bad = {"price_min": 900 * MILLION, "price_max": 100 * MILLION}
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, bad)])

    cache = DictCache()
    parser = make_parser(build_intent_agent(FunctionModel(always_invalid)), cache)
    parsed = await parser.parse("۲۰۶ تهران")
    assert parsed.parsed_by is ParsedBy.RULES
    assert cache.values == {}


async def test_slow_llm_times_out_into_the_rules_parser() -> None:
    async def too_slow(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        await asyncio.sleep(5)
        raise AssertionError("unreachable")

    parser = make_parser(build_intent_agent(FunctionModel(too_slow)), DictCache(), 0.05)
    assert (await parser.parse("۲۰۶ تهران")).parsed_by is ParsedBy.RULES


async def test_empty_query_is_browse_mode_without_touching_the_llm() -> None:
    parsed = await make_parser(agent_returning(LLM_OUTPUT), DictCache()).parse("   ")
    assert parsed.intent == SearchIntent()


def test_instructions_state_the_current_jalali_year() -> None:
    assert "The current Jalali year is 14" in build_instructions()


@pytest.mark.parametrize("field", ["price_min", "year_min"])
def test_search_intent_rejects_inverted_ranges(field: str) -> None:
    other = field.replace("min", "max")
    values = {"price_min": 900, "price_max": 100, "year_min": 1400, "year_max": 1390}
    with pytest.raises(ValueError, match="must not exceed"):
        SearchIntent(**{field: values[field], other: values[other]})
