"""The shopping-assistant agent (spec 3 §3.4). Its two tools call the existing search
and listing services; its only output type is AssistantReply. It never writes SQL."""

import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.models import Model

from repositories.listing_repository import ListingRepository
from schemas.assistant import AssistantMessage
from schemas.listing import ListingCard
from schemas.search import SearchIntent
from services.listing_views import to_card
from services.search_service import SearchService

OUTPUT_RETRIES = 2
TOOL_RESULT_LIMIT = 8
FIRST_PAGE = 1
_CARD_FIELDS = {
    "id",
    "title",
    "trim",
    "year",
    "km",
    "price",
    "city",
    "gearbox",
    "est_price",
    "diff_pct",
    "deal_score",
    "verdict",
    "is_exact",
    "near_miss_labels",
}

_INSTRUCTIONS = """\
You are ترب‌کار's shopping assistant for used vehicles on Divar (Iran). Answer in
short, friendly Persian (2–4 sentences), in the same informal register as the user.

- To find vehicles call `search_listings` with a SearchIntent built from the user's
  words: years are Jalali, money is toman as a full integer (۸۰۰ میلیون = 800000000),
  km_max in kilometres, vehicles as the user wrote them. Never invent listings.
- To judge "which is better" between the vehicles the user is comparing, call
  `compare_listings` with the compare ids given in the prompt; prefer the highest
  deal_score and explain why (price vs. estimate, km, year).
- Put the ids of the listings you mention in `listing_ids` (at most 3), in the
  order you recommend them. Mention prices in میلیون/میلیارد تومان words.
- If nothing matches, say so and suggest one concrete relaxation (higher budget,
  another city, older model). Do not answer questions unrelated to buying a vehicle.
"""


@dataclass(frozen=True, slots=True)
class AssistantDeps:
    search: SearchService
    listings: ListingRepository


class AssistantReply(BaseModel):
    text: str
    listing_ids: list[uuid.UUID] = Field(default_factory=list, max_length=3)


def _brief(card: ListingCard) -> dict[str, Any]:
    return card.model_dump(mode="json", include=_CARD_FIELDS)


def build_prompt(messages: list[AssistantMessage], compare_ids: list[uuid.UUID]) -> str:
    """The stateless request as one prompt: the (capped) history, then the question."""
    history = "\n".join(f"{message.role.value}: {message.text}" for message in messages)
    compare = ", ".join(str(listing_id) for listing_id in compare_ids) or "none"
    return f"Conversation so far:\n{history}\n\nCompare ids: {compare}"


def build_assistant_agent(model: Model) -> Agent[AssistantDeps, AssistantReply]:
    agent: Agent[AssistantDeps, AssistantReply] = Agent(
        model,
        deps_type=AssistantDeps,
        output_type=AssistantReply,
        instructions=_INSTRUCTIONS,
        retries=OUTPUT_RETRIES,
    )

    @agent.tool
    async def search_listings(
        context: RunContext[AssistantDeps], intent: SearchIntent
    ) -> dict[str, Any]:
        """Search the live listings; returns the total and the best matches."""
        ranked, _ = await context.deps.search.rank(intent)
        cards = await context.deps.search.page_of(
            ranked.results, FIRST_PAGE, TOOL_RESULT_LIMIT
        )
        return {
            "total": len(ranked.results),
            "exact_count": sum(item.is_exact for item in ranked.results),
            "listings": [_brief(card) for card in cards],
        }

    @agent.tool
    async def compare_listings(
        context: RunContext[AssistantDeps], listing_ids: list[uuid.UUID]
    ) -> list[dict[str, Any]]:
        """The listings the user is comparing, with their price verdicts."""
        found = await context.deps.listings.get_by_ids(listing_ids)
        return [_brief(to_card(listing)) for listing in found]

    return agent
