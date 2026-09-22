"""Free text → SearchIntent: cache → LLM → rules fallback (spec §8.3)."""

import asyncio
import hashlib
import logging
from dataclasses import dataclass

import httpx
from pydantic import ValidationError
from pydantic_ai import Agent
from pydantic_ai.exceptions import AgentRunError, ModelAPIError

from core.cache import Cache
from core.text import normalize_persian
from enums import ParsedBy
from errors import invalid_search_error
from llm.rules_parser import parse_with_rules
from repositories.city_repository import CityRepository
from schemas.search import SearchIntent

logger = logging.getLogger(__name__)

PROMPT_VERSION = "v2"  # bump when llm/intent_agent.py instructions change
LLM_FAILURES = (AgentRunError, ModelAPIError, TimeoutError, httpx.HTTPError)


@dataclass(frozen=True, slots=True)
class ParsedQuery:
    intent: SearchIntent
    parsed_by: ParsedBy


def _cache_key(query: str) -> str:
    digest = hashlib.sha256(query.encode()).hexdigest()
    return f"intent:{PROMPT_VERSION}:{digest}"


class QueryParser:
    def __init__(
        self,
        agent: Agent[None, SearchIntent] | None,
        cities: CityRepository,
        cache: Cache,
        timeout_seconds: float,
        cache_ttl_seconds: int,
    ) -> None:
        self._agent = agent
        self._cities = cities
        self._cache = cache
        self._timeout_seconds = timeout_seconds
        self._cache_ttl_seconds = cache_ttl_seconds

    async def parse(self, text: str) -> ParsedQuery:
        query = normalize_persian(text)
        if not query:
            return ParsedQuery(SearchIntent(), ParsedBy.RULES)
        cached = await self._cache.get_json(_cache_key(query))
        if cached is not None:
            return ParsedQuery(SearchIntent.model_validate(cached), ParsedBy.LLM)
        intent = await self._ask_llm(query)
        if intent is None:
            # Fallback results are not cached, so the next request retries the LLM.
            known_cities = await self._cities.list_names()
            try:
                rules_intent = parse_with_rules(query, known_cities)
            except ValidationError as error:
                raise invalid_search_error("Invalid search filters", error) from error
            return ParsedQuery(rules_intent, ParsedBy.RULES)
        payload = intent.model_dump(mode="json")
        await self._cache.set_json(_cache_key(query), payload, self._cache_ttl_seconds)
        return ParsedQuery(intent, ParsedBy.LLM)

    async def _ask_llm(self, query: str) -> SearchIntent | None:
        """None means "use the rules parser". An LLM outage must never fail a search,
        so provider errors are logged and absorbed here — deliberately."""
        if self._agent is None:
            return None
        try:
            result = await asyncio.wait_for(
                self._agent.run(query), self._timeout_seconds
            )
        except LLM_FAILURES as error:
            fields = {"error": type(error).__name__, "detail": str(error)}
            logger.warning("llm parse failed, using rules", extra={"fields": fields})
            return None
        return result.output
