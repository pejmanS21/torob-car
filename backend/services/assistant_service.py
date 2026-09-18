"""POST /assistant: LLM agent first, deterministic rules reply when there is no key,
a timeout or a provider error (spec 3 §3.4)."""

import asyncio
import logging
import re
import statistics
import uuid

from pydantic_ai import Agent

from core.text import to_persian_digits
from enums import ParsedBy
from llm.assistant_agent import AssistantDeps, AssistantReply, build_prompt
from ranking import labels
from ranking.weights import CHEAP_DIFF_PCT
from repositories.listing_repository import ListingRepository
from schemas.assistant import AssistantRequest, AssistantResponse
from schemas.listing import ListingCard
from services.listing_views import to_card
from services.query_parser import LLM_FAILURES, QueryParser
from services.search_service import MAX_RESULTS, SearchService

logger = logging.getLogger(__name__)

SUGGESTED_CARDS = 3
MIN_CARDS_TO_COMPARE = 2
FIRST_PAGE = 1
COMPARE_QUESTION = re.compile(r"کدوم|کدام|بهتر|به\s?صرفه")
NO_MATCH_TEXT = (
    "با این شرایط آگهی فعالی نداریم. سقف قیمت را بالاتر ببر یا شهر را حذف کن."
)


def _deal_score_or_lowest(card: ListingCard) -> int:
    return card.deal_score if card.deal_score is not None else -1


def _exact_then_best_deal(card: ListingCard) -> tuple[bool, int]:
    """Exact matches before near-misses, then the best deal (same tiers as search)."""
    return card.is_exact, _deal_score_or_lowest(card)


class AssistantService:
    def __init__(
        self,
        agent: Agent[AssistantDeps, AssistantReply] | None,
        parser: QueryParser,
        search: SearchService,
        listings: ListingRepository,
        timeout_seconds: float,
    ) -> None:
        self._agent = agent
        self._parser = parser
        self._search = search
        self._listings = listings
        self._timeout_seconds = timeout_seconds

    async def reply(self, request: AssistantRequest) -> AssistantResponse:
        reply = await self._ask_llm(request)
        if reply is None:
            return await self._rules_reply(request)
        cards = await self._cards(reply.listing_ids)
        return AssistantResponse(
            text=reply.text, listings=cards, answered_by=ParsedBy.LLM
        )

    async def _ask_llm(self, request: AssistantRequest) -> AssistantReply | None:
        """None means "use the rules reply". Like QueryParser, an LLM outage must
        never fail the chat, so provider errors are logged and absorbed here."""
        if self._agent is None:
            return None
        deps = AssistantDeps(self._search, self._listings)
        prompt = build_prompt(request.messages, request.compare_ids)
        try:
            result = await asyncio.wait_for(
                self._agent.run(prompt, deps=deps), self._timeout_seconds
            )
        except LLM_FAILURES as error:
            fields = {"error": type(error).__name__, "detail": str(error)}
            logger.warning(
                "assistant llm failed, using rules", extra={"fields": fields}
            )
            return None
        return result.output

    async def _cards(self, listing_ids: list[uuid.UUID]) -> list[ListingCard]:
        found = await self._listings.get_by_ids(listing_ids)
        return [to_card(listing) for listing in found]

    async def _rules_reply(self, request: AssistantRequest) -> AssistantResponse:
        compared = await self._cards(request.compare_ids)
        if COMPARE_QUESTION.search(request.question) and (
            len(compared) >= MIN_CARDS_TO_COMPARE
        ):
            return _best_of(compared)
        parsed = await self._parser.parse(request.question)
        ranked, _ = await self._search.rank(parsed.intent)
        # ponytail: hydrates every ranked card (≤ MAX_RESULTS) for the median; a
        # price-stats repository query would do if this shows up in latency logs.
        cards = await self._search.page_of(ranked.results, FIRST_PAGE, MAX_RESULTS)
        if not cards:
            return AssistantResponse(
                text=NO_MATCH_TEXT, listings=[], answered_by=ParsedBy.RULES
            )
        return _summary_of(cards, ranked.chips)


def _best_of(compared: list[ListingCard]) -> AssistantResponse:
    best = max(compared, key=_deal_score_or_lowest)
    score = to_persian_digits(best.deal_score) if best.deal_score is not None else "—"
    count = to_persian_digits(len(compared))
    text = (
        f"بین {count} خودرویی که مقایسه می‌کنی، «{best.title}» "
        f"بهترین ارزش خرید را دارد (امتیاز {score}/۱۰۰)."
    )
    return AssistantResponse(text=text, listings=[best], answered_by=ParsedBy.RULES)


def _summary_of(cards: list[ListingCard], chips: tuple[str, ...]) -> AssistantResponse:
    prices = [card.price for card in cards if card.price is not None]
    below = sum(1 for card in cards if (card.diff_pct or 0) <= CHEAP_DIFF_PCT)
    median = labels.format_toman(round(statistics.median(prices))) if prices else "—"
    understood = f" ({'، '.join(chips)})" if chips else ""
    text = (
        f"{to_persian_digits(len(cards))} آگهی پیدا کردم{understood}. "
        f"میانهٔ قیمت‌شان {median} است و {to_persian_digits(below)} تا زیر قیمت بازار. "
        "سه‌تای اول از نظر ارزش خرید:"
    )
    top = sorted(cards, key=_exact_then_best_deal, reverse=True)[:SUGGESTED_CARDS]
    return AssistantResponse(text=text, listings=top, answered_by=ParsedBy.RULES)
