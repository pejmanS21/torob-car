"""POST /assistant: the LLM agent answers, or the request fails.

There is deliberately no canned reply here. A sentence this service wrote itself is
indistinguishable, in the chat bubble, from one the model wrote — so an outage surfaces
as 503 `assistant_unavailable` and the UI says the assistant is unreachable, rather than
inventing an answer in its voice.
"""

import asyncio
import logging
from collections.abc import AsyncIterator

from pydantic_ai import Agent
from pydantic_ai.run import AgentRunResultEvent

from core.persian_prose import format_persian_prose
from enums import ParsedBy
from errors import AssistantUnavailableError
from llm.assistant_agent import (
    AssistantDeps,
    AssistantReply,
    build_prompt,
    comparison_ids,
)
from llm.assistant_stream import AssistantTextStream
from repositories.listing_repository import ListingRepository
from schemas.assistant import AssistantRequest, AssistantResponse, AssistantTextUpdate
from services.query_parser import LLM_FAILURES
from services.search_service import SearchService

logger = logging.getLogger(__name__)


class AssistantService:
    def __init__(
        self,
        agent: Agent[AssistantDeps, AssistantReply] | None,
        search: SearchService,
        listings: ListingRepository,
        timeout_seconds: float,
    ) -> None:
        self._agent = agent
        self._search = search
        self._listings = listings
        self._timeout_seconds = timeout_seconds

    async def reply(self, request: AssistantRequest) -> AssistantResponse:
        deps = self._deps(request)
        answer = await self._ask_llm(request, deps)
        return self._response(answer, deps)

    @staticmethod
    def _response(answer: AssistantReply, deps: AssistantDeps) -> AssistantResponse:
        # Keep the exact cards the model saw, including their search match metadata.
        cards = [deps.seen_cards[key] for key in dict.fromkeys(answer.listing_ids)]
        return AssistantResponse(
            text=format_persian_prose(answer.text),
            listings=cards,
            answered_by=ParsedBy.LLM,
        )

    async def stream(
        self, request: AssistantRequest
    ) -> AsyncIterator[AssistantTextUpdate | AssistantResponse]:
        if self._agent is None:
            raise AssistantUnavailableError()
        prompt = build_prompt(request.messages, request.compare_ids)
        deps = self._deps(request)
        answer = None
        text_stream = AssistantTextStream()
        try:
            async with asyncio.timeout(self._timeout_seconds):
                async with self._agent.run_stream_events(prompt, deps=deps) as events:
                    async for event in events:
                        if isinstance(event, AgentRunResultEvent):
                            answer = event.result.output
                        elif (text := text_stream.update(event)) is not None:
                            yield AssistantTextUpdate(text=text)
        except LLM_FAILURES as error:
            logger.warning(
                "assistant stream failed",
                extra={"fields": {"error": type(error).__name__}},
            )
            raise AssistantUnavailableError() from error
        if answer is None:
            raise AssistantUnavailableError()
        yield self._response(answer, deps)

    def _deps(self, request: AssistantRequest) -> AssistantDeps:
        return AssistantDeps(
            self._search,
            self._listings,
            comparison_ids(request.messages, request.compare_ids),
        )

    async def _ask_llm(
        self, request: AssistantRequest, deps: AssistantDeps
    ) -> AssistantReply:
        """Every failure ends the same way: no key, a timeout and a provider error all
        mean "the assistant is unreachable", and none of them invent a reply."""
        if self._agent is None:
            logger.warning("assistant asked with no model configured")
            raise AssistantUnavailableError()
        prompt = build_prompt(request.messages, request.compare_ids)
        try:
            result = await asyncio.wait_for(
                self._agent.run(prompt, deps=deps), self._timeout_seconds
            )
        except LLM_FAILURES as error:
            fields = {"error": type(error).__name__, "detail": str(error)}
            logger.warning("assistant llm failed", extra={"fields": fields})
            raise AssistantUnavailableError() from error
        return result.output
