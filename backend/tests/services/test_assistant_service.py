"""AssistantService in isolation: rules path with stubs, LLM path with a
FunctionModel that calls the search tool. No test reaches a provider."""

import uuid
from datetime import UTC, datetime

from pydantic_ai import ModelMessage, ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.exceptions import ModelAPIError
from pydantic_ai.models.function import AgentInfo, FunctionModel

from enums import Category, ChatRole, ParsedBy, Verdict
from llm.assistant_agent import build_assistant_agent
from ranking.types import RankedListing
from schemas.assistant import AssistantMessage, AssistantRequest
from schemas.listing import ListingCard
from schemas.search import SearchIntent
from services.assistant_service import AssistantService
from services.query_parser import ParsedQuery
from services.search_service import RankedSearch

NOW = datetime(2026, 9, 17, 20, 0, tzinfo=UTC)
IDS = [uuid.UUID(int=number) for number in range(1, 4)]
MILLION = 1_000_000


def make_card(listing_id: uuid.UUID, price: int, deal_score: int | None) -> ListingCard:
    return ListingCard(
        id=listing_id,
        token=f"tok{listing_id.int}",
        title=f"پژو ۲۰۶ شمارهٔ {listing_id.int}",
        category=Category.LIGHT,
        brand="پژو",
        model="پژو 206",
        trim="پژو 206 تیپ ۲",
        year=1398,
        km=60_000,
        price=price,
        city="تهران",
        district=None,
        lat=None,
        lng=None,
        gearbox=None,
        fuel=None,
        body_condition=None,
        insurance_months=None,
        thumbnail_url=None,
        posted_at=NOW,
        est_price=900 * MILLION,
        diff_pct=(price - 900 * MILLION) / (900 * MILLION) * 100,
        deal_score=deal_score,
        verdict=Verdict.FAIR,
    )


CARDS = {
    IDS[0]: make_card(IDS[0], 800 * MILLION, 90),
    IDS[1]: make_card(IDS[1], 900 * MILLION, 50),
    IDS[2]: make_card(IDS[2], 1_000 * MILLION, None),
}


class StubParser:
    async def parse(self, text: str) -> ParsedQuery:
        return ParsedQuery(SearchIntent(text=text), ParsedBy.RULES)


class StubSearch:
    def __init__(self, ids: list[uuid.UUID]) -> None:
        self.ids = ids
        self.intents: list[SearchIntent] = []

    async def rank(
        self, intent: SearchIntent, exclude_id: uuid.UUID | None = None
    ) -> tuple[RankedSearch, bool]:
        self.intents.append(intent)
        results = tuple(RankedListing(i, 1.0, 1.0, True, ()) for i in self.ids)
        return RankedSearch(("پژو 206",), results), False

    async def page_of(
        self, results: tuple[RankedListing, ...], page: int, page_size: int
    ) -> list[ListingCard]:
        return [CARDS[item.id] for item in results[:page_size]]


class StubListings:
    async def get_by_ids(self, listing_ids: list[uuid.UUID]) -> list[object]:
        return [_as_orm(CARDS[i]) for i in listing_ids if i in CARDS]


class _AsOrm:
    """Just enough of a Listing for to_card()."""

    def __init__(self, card: ListingCard) -> None:
        self.__dict__.update(card.model_dump(exclude={"brand", "model", "trim"}))
        self.thumbnail_urls: list[str] = []
        self.image_urls: list[str] = []
        self.city = type("City", (), {"name": card.city, "lat": None, "lng": None})()
        self.catalog = type(
            "Catalog", (), {"brand": card.brand, "model": card.model, "trim": card.trim}
        )()


def _as_orm(card: ListingCard) -> _AsOrm:
    return _AsOrm(card)


def ask(text: str, compare_ids: list[uuid.UUID] | None = None) -> AssistantRequest:
    return AssistantRequest(
        messages=[AssistantMessage(role=ChatRole.USER, text=text)],
        compare_ids=compare_ids or [],
    )


def make_service(agent, search: StubSearch) -> AssistantService:
    return AssistantService(agent, StubParser(), search, StubListings(), 1.0)


async def test_rules_reply_counts_medians_and_ranks_by_deal_score() -> None:
    response = await make_service(None, StubSearch(IDS)).reply(ask("۲۰۶ تهران"))
    assert response.answered_by is ParsedBy.RULES
    assert "۳ آگهی پیدا کردم (پژو 206)" in response.text
    assert "۹۰۰ میلیون" in response.text  # median of 800/900/1000 million
    assert "۱ تا زیر قیمت بازار" in response.text
    assert [card.id for card in response.listings] == [IDS[0], IDS[1], IDS[2]]


async def test_rules_reply_without_matches_suggests_a_relaxation() -> None:
    response = await make_service(None, StubSearch([])).reply(
        ask("تارا زیر ۱۰۰ میلیون")
    )
    assert response.listings == [] and "آگهی فعالی نداریم" in response.text


async def test_which_is_better_picks_the_highest_deal_score_among_compared() -> None:
    service = make_service(None, StubSearch(IDS))
    response = await service.reply(
        ask("کدوم به‌صرفه‌تره؟", compare_ids=[IDS[1], IDS[0]])
    )
    assert [card.id for card in response.listings] == [IDS[0]]
    assert "امتیاز ۹۰" in response.text


async def test_llm_path_calls_the_search_tool_and_hydrates_cards() -> None:
    def scripted(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        returned = [
            part
            for message in messages
            for part in message.parts
            if isinstance(part, ToolReturnPart)
        ]
        if not returned:
            intent = {"vehicles": [{"model": "۲۰۶"}], "cities": ["تهران"]}
            return ModelResponse(
                parts=[ToolCallPart("search_listings", {"intent": intent})]
            )
        found = returned[0].content["listings"]
        reply = {"text": "این‌ها را ببین", "listing_ids": [found[0]["id"]]}
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, reply)])

    search = StubSearch(IDS)
    service = make_service(build_assistant_agent(FunctionModel(scripted)), search)
    response = await service.reply(ask("یه ۲۰۶ تو تهران"))
    assert response.answered_by is ParsedBy.LLM
    assert response.text == "این‌ها را ببین"
    assert [card.id for card in response.listings] == [IDS[0]]
    assert search.intents[0].cities == ["تهران"]


async def test_llm_failure_falls_back_to_the_rules_reply() -> None:
    def broken(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        raise ModelAPIError("function-model", "provider down")

    service = make_service(
        build_assistant_agent(FunctionModel(broken)), StubSearch(IDS)
    )
    response = await service.reply(ask("۲۰۶ تهران"))
    assert response.answered_by is ParsedBy.RULES
