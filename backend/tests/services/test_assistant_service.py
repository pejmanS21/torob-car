"""AssistantService in isolation: the LLM path with a FunctionModel that calls the
search tool, and the two ways it can be unavailable. No test reaches a provider."""

import asyncio
import json
import uuid
from datetime import UTC, datetime

import pytest
from pydantic_ai import (
    ModelMessage,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.exceptions import ModelAPIError
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, FunctionModel

from enums import (
    BodyCondition,
    Category,
    ChatRole,
    EstimateBasis,
    Fuel,
    Gearbox,
    ParsedBy,
    PriceType,
    Source,
    Verdict,
)
from errors import AssistantUnavailableError
from llm.assistant_agent import (
    _brief,
    build_assistant_agent,
    build_prompt,
    comparison_ids,
)
from ranking.types import RankedListing
from schemas.assistant import (
    AssistantMessage,
    AssistantRequest,
    AssistantResponse,
    AssistantTextUpdate,
)
from schemas.listing import ListingCard
from schemas.search import SearchIntent
from services.assistant_service import AssistantService
from services.search_service import RankedSearch

NOW = datetime(2026, 9, 17, 20, 0, tzinfo=UTC)
IDS = [uuid.UUID(int=number) for number in range(1, 4)]
MILLION = 1_000_000


def make_card(listing_id: uuid.UUID, price: int, deal_score: int | None) -> ListingCard:
    return ListingCard(
        id=listing_id,
        token=f"tok{listing_id.int}",
        title=f"پژو ۲۰۶ شمارهٔ {listing_id.int}",
        source=Source.DIVAR,
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


def test_listing_tool_preserves_known_details_and_unknowns() -> None:
    card = CARDS[IDS[0]].model_copy(
        update={
            "title": "دنا پلاس اتوماتیک گارانتی فعال",
            "model": "دنا پلاس",
            "trim": "دنا پلاس اتوماتیک",
            "gearbox": Gearbox.AUTOMATIC,
            "fuel": Fuel.PETROL,
            "body_condition": BodyCondition.NO_PAINT,
            "insurance_months": 6,
        }
    )
    details = _brief(card)
    assert details["model"] == "دنا پلاس"
    assert details["trim"] == "دنا پلاس اتوماتیک"
    assert details["fuel"] == "petrol"
    assert details["body_condition"] == "no_paint"
    assert details["insurance_months"] == 6
    assert details["price"] == card.price
    assert details["est_price"] == card.est_price
    unknown = _brief(CARDS[IDS[2]])
    assert unknown["fuel"] is None
    assert unknown["body_condition"] is None
    assert unknown["insurance_months"] is None
    assert unknown["deal_score"] is None


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
        return [
            CARDS[item.id].model_copy(
                update={
                    "match_score": item.match,
                    "is_exact": item.is_exact,
                    "near_miss_labels": list(item.labels),
                }
            )
            for item in results[:page_size]
        ]


class StubListings:
    async def get_by_ids(self, listing_ids: list[uuid.UUID]) -> list[object]:
        return [_as_orm(CARDS[i]) for i in listing_ids if i in CARDS]


class _AsOrm:
    """Just enough of a Listing for to_card()."""

    def __init__(self, card: ListingCard) -> None:
        self.__dict__.update(card.model_dump(exclude={"brand", "model", "trim"}))
        self.thumbnail_urls: list[str] = []
        self.image_urls: list[str] = []
        self.url = "https://example.com/listing"
        self.description = "فروش اقساطی، تماس ۰۹۱۲۳۴۵۶۷۸۹"
        self.color = None
        self.is_dealer = False
        self.price_type = PriceType.INSTALLMENT
        self.document_status = None
        self.attributes = {"حواله": "دارد"}
        self.km_factor = 1.0
        self.insurance_factor = 1.0
        self.est_basis = EstimateBasis.TRIM_YEAR
        self.est_sample_size = 10
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
    return AssistantService(agent, search, StubListings(), 1.0)


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
        assert found[0]["price_type"] == "installment"
        assert found[0]["attributes"] == {"حواله": "دارد"}
        assert "اقساطی" in found[0]["description_excerpt"]
        assert "۰۹۱۲۳۴۵۶۷۸۹" not in found[0]["description_excerpt"]
        reply = {
            "text": "این‌ها را ببین",
            "listing_ids": [found[1]["id"], found[0]["id"], found[1]["id"]],
        }
        # PromptedOutput: the reply comes back as JSON text, not an output tool call.
        return ModelResponse(parts=[TextPart(json.dumps(reply, ensure_ascii=False))])

    search = StubSearch(IDS)
    service = make_service(build_assistant_agent(FunctionModel(scripted)), search)
    response = await service.reply(ask("یه ۲۰۶ تو تهران"))
    assert response.answered_by is ParsedBy.LLM
    assert response.text == "این‌ها را ببین"
    assert [card.id for card in response.listings] == [IDS[1], IDS[0]]
    assert all(card.match_score == 1.0 for card in response.listings)
    assert search.intents[0].cities == ["تهران"]


async def test_a_provider_failure_is_reported_never_answered_from_a_script() -> None:
    def broken(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        raise ModelAPIError("function-model", "provider down")

    service = make_service(
        build_assistant_agent(FunctionModel(broken)), StubSearch(IDS)
    )
    with pytest.raises(AssistantUnavailableError):
        await service.reply(ask("۲۰۶ تهران"))


async def test_no_configured_model_is_reported_too() -> None:
    with pytest.raises(AssistantUnavailableError):
        await make_service(None, StubSearch(IDS)).reply(ask("۲۰۶ تهران"))


async def test_followup_compares_previous_recommendations_not_the_tray() -> None:
    def scripted(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        returned = [
            part.content
            for message in messages
            for part in message.parts
            if isinstance(part, ToolReturnPart)
        ]
        if not returned:
            return ModelResponse(parts=[ToolCallPart("compare_listings", {})])
        assert {card["id"] for card in returned[0]} == {str(IDS[0]), str(IDS[1])}
        assert all(card["price_type"] == "installment" for card in returned[0])
        best = max(returned[0], key=lambda card: card["deal_score"])
        return ModelResponse(
            parts=[
                TextPart(
                    json.dumps(
                        {"text": "۲۰۶ اول به‌صرفه‌تره", "listing_ids": [best["id"]]}
                    )
                )
            ]
        )

    request = AssistantRequest(
        messages=[
            AssistantMessage(role=ChatRole.USER, text="پژو ۲۰۶ تیپ ۲ تهران"),
            AssistantMessage(
                role=ChatRole.ASSISTANT, text="این‌ها رو پیدا کردم", listing_ids=IDS[:2]
            ),
            AssistantMessage(role=ChatRole.USER, text="بین این‌ها کدوم به‌صرفه‌تره؟"),
        ],
        compare_ids=[IDS[2]],
    )
    search = StubSearch(IDS)
    result = await make_service(
        build_assistant_agent(FunctionModel(scripted)), search
    ).reply(request)
    assert [card.id for card in result.listings] == [IDS[0]]
    assert search.intents == []


def test_missing_history_ids_never_fall_back_to_unrelated_tray() -> None:
    messages = [
        AssistantMessage(role=ChatRole.USER, text="۲۰۶ تهران"),
        AssistantMessage(role=ChatRole.ASSISTANT, text="این‌ها رو ببین"),
        AssistantMessage(role=ChatRole.USER, text="کدوم بهتره؟"),
    ]
    assert comparison_ids(messages, IDS) == ()
    assert comparison_ids(messages[:1], IDS) == tuple(IDS)


def test_prompt_distinguishes_search_results_from_background_selections() -> None:
    request = ask("۲۰۶ تهران", IDS)
    prompt = json.loads(build_prompt(request.messages, request.compare_ids))
    assert prompt["conversation"] == [
        {"role": "user", "text": "۲۰۶ تهران", "listing_ids": []}
    ]
    assert prompt["comparison_tray_background_only"] == [str(i) for i in IDS]


async def test_ungrounded_listing_ids_are_rejected() -> None:
    def invented(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(
            parts=[
                TextPart(
                    json.dumps({"text": "این رو بخر", "listing_ids": [str(IDS[0])]})
                )
            ]
        )

    service = make_service(
        build_assistant_agent(FunctionModel(invented)), StubSearch(IDS)
    )
    with pytest.raises(AssistantUnavailableError):
        await service.reply(ask("۲۰۶ تهران"))


@pytest.mark.parametrize("has_exact", [True, False])
async def test_automatic_search_never_offers_manual_or_unknown_gearboxes(
    has_exact: bool,
) -> None:
    class DenaSearch(StubSearch):
        async def rank(
            self, intent: SearchIntent, exclude_id: uuid.UUID | None = None
        ) -> tuple[RankedSearch, bool]:
            assert intent.gearbox is Gearbox.AUTOMATIC
            results = (
                RankedListing(IDS[0], 0.9, 1.0, has_exact, ()),
                RankedListing(IDS[1], 0.8, 0.8, False, ("دنده‌ای",)),
                RankedListing(IDS[2], 0.7, 0.9, False, ()),
            )
            return RankedSearch(("دنا پلاس", "اتوماتیک"), results), False

        async def page_of(
            self, results: tuple[RankedListing, ...], page: int, page_size: int
        ) -> list[ListingCard]:
            cards = await super().page_of(results, page, page_size)
            gearboxes = dict(
                zip(IDS, [Gearbox.AUTOMATIC, Gearbox.MANUAL, None], strict=True)
            )
            return [
                card.model_copy(
                    update={"model": "دنا پلاس", "gearbox": gearboxes[card.id]}
                )
                for card in cards
            ]

    def scripted(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        returned = [
            part.content
            for message in messages
            for part in message.parts
            if isinstance(part, ToolReturnPart)
        ]
        if not returned:
            intent = {"vehicles": [{"model": "دنا پلاس"}], "gearbox": "automatic"}
            return ModelResponse(
                parts=[ToolCallPart("search_listings", {"intent": intent})]
            )
        result = returned[0]
        assert result["total"] == result["exact_count"] == int(has_exact)
        assert result["near_miss_count"] == 3 - int(has_exact)
        assert result["applied_filters"] == ["دنا پلاس", "اتوماتیک"]
        assert all(card["gearbox"] == "automatic" for card in result["listings"])
        reply = {
            "text": "این مورد رو پیدا کردم" if has_exact else "مورد مطابق پیدا نشد",
            "listing_ids": [card["id"] for card in result["listings"]],
        }
        return ModelResponse(parts=[TextPart(json.dumps(reply))])

    service = make_service(
        build_assistant_agent(FunctionModel(scripted)), DenaSearch(IDS)
    )
    result = await service.reply(ask("دنا پلاس اتمات"))
    assert [card.id for card in result.listings] == ([IDS[0]] if has_exact else [])
    assert all(card.match_score == 1.0 for card in result.listings)


async def test_stream_emits_persian_before_completion_then_real_cards() -> None:
    finish = asyncio.Event()
    updates = asyncio.Queue()

    async def streamed(messages, info):
        returned = [
            part
            for message in messages
            for part in message.parts
            if isinstance(part, ToolReturnPart)
        ]
        if not returned:
            yield {
                0: DeltaToolCall(
                    name="search_listings", json_args='{"intent":{"text":"۲۰۶"}}'
                )
            }
            return
        yield '{"text":"بهصرفهبودن'
        await finish.wait()
        yield ' مهم است.","listing_ids":["' + str(IDS[0]) + '"]}'

    service = make_service(
        build_assistant_agent(FunctionModel(stream_function=streamed)), StubSearch(IDS)
    )

    async def consume():
        async for update in service.stream(ask("۲۰۶ تهران")):
            await updates.put(update)

    task = asyncio.create_task(consume())
    try:
        first = await asyncio.wait_for(updates.get(), 0.8)
        assert isinstance(first, AssistantTextUpdate)
        assert first.text == "به‌صرفه بودن"
        assert not task.done()
    finally:
        finish.set()
        await task
    remaining = []
    while not updates.empty():
        remaining.append(updates.get_nowait())
    assert isinstance(remaining[-1], AssistantResponse)
    assert remaining[-1].text == "به‌صرفه بودن مهم است."
    assert [card.id for card in remaining[-1].listings] == [IDS[0]]
    assert remaining[-1].listings[0].match_score == 1.0


async def test_stream_provider_failure_is_not_a_completed_answer() -> None:
    async def broken(messages, info):
        yield '{"text":"سلام'
        raise ModelAPIError("function-model", "provider disconnected")

    service = make_service(
        build_assistant_agent(FunctionModel(stream_function=broken)), StubSearch(IDS)
    )
    with pytest.raises(AssistantUnavailableError):
        async for _ in service.stream(ask("سلام")):
            pass


async def test_stream_retries_ungrounded_ids_and_only_returns_validated_cards() -> None:
    attempts = 0

    async def streamed(messages, info):
        nonlocal attempts
        returned = [
            part
            for message in messages
            for part in message.parts
            if isinstance(part, ToolReturnPart)
        ]
        if not returned:
            yield {
                0: DeltaToolCall(
                    name="search_listings", json_args='{"intent":{"text":"۲۰۶"}}'
                )
            }
            return
        attempts += 1
        listing_id = uuid.UUID(int=999) if attempts == 1 else IDS[0]
        yield json.dumps({"text": "این گزینه بهتره", "listing_ids": [str(listing_id)]})

    service = make_service(
        build_assistant_agent(FunctionModel(stream_function=streamed)), StubSearch(IDS)
    )
    updates = [update async for update in service.stream(ask("۲۰۶ تهران"))]
    assert attempts == 2
    assert [card.id for card in updates[-1].listings] == [IDS[0]]
