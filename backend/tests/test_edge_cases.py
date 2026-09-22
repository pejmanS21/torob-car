from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import UUID

import pytest
from httpx import AsyncClient
from pydantic import ValidationError
from pydantic_ai.messages import PartStartEvent, TextPart
from sqlalchemy.ext.asyncio import AsyncSession

from api.assistant_stream import assistant_events
from dependencies.providers import get_audit_recorder
from enums import Fuel, Gearbox, MentionLevel
from errors import AssistantUnavailableError, IngestError
from ingest.column_maps import PRICE_TYPE_COLUMN, UnknownValueError
from ingest.pipeline import IngestPipeline
from ingest.row_mapper import map_row
from llm.assistant_stream import AssistantTextStream
from llm.rules_parser import parse_with_rules
from ranking.types import VehicleTarget
from schemas.assistant import AssistantMessage, AssistantTextUpdate
from schemas.search import SearchIntent, SearchOverrides
from services.assistant_service import AssistantService
from services.intent_chips import build_chips
from tests.ingest.test_row_mapper import BASE_ROW
from tests.services.test_assistant_service import ask


async def test_empty_assistant_stream_rolls_back() -> None:
    session = AsyncMock()

    async def updates() -> AsyncIterator[AssistantTextUpdate]:
        yield AssistantTextUpdate(text="partial")

    events = [event async for event in assistant_events(updates(), session)]
    assert "event: error" in events[-1]
    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()


@pytest.mark.parametrize("raw", ["not json", "[]", '{"text": 1}'])
def test_partial_model_json_never_leaks(raw: str) -> None:
    assert (
        AssistantTextStream().update(PartStartEvent(index=0, part=TextPart(raw)))
        is None
    )


async def test_incomplete_agent_is_unavailable() -> None:
    @asynccontextmanager
    async def run_stream_events(
        *args: object, **kwargs: object
    ) -> AsyncIterator[AsyncIterator[PartStartEvent]]:
        async def events() -> AsyncIterator[PartStartEvent]:
            yield PartStartEvent(index=0, part=TextPart("{}"))

        yield events()

    for agent in (None, SimpleNamespace(run_stream_events=run_stream_events)):
        service = AssistantService(agent, Mock(), Mock(), 1)
        with pytest.raises(AssistantUnavailableError):
            _ = [update async for update in service.stream(ask("پژو"))]


async def test_ingest_empty_and_rejected_files(tmp_path: Path) -> None:
    cities, catalog, listings, cache = (AsyncMock() for _ in range(4))
    listings.newest_fetched_at.return_value = None
    cache.bump_data_version.return_value = 1
    pipeline = IngestPipeline(cities, catalog, listings, cache)
    csv = tmp_path / "empty.csv"
    csv.write_text("token\n")
    report = await pipeline.run(csv)
    assert report.rows_read == 0
    listings.load_estimator_inputs.assert_not_awaited()
    csv.write_text("token\nbad\n")
    with pytest.raises(IngestError):
        await pipeline.run(csv)
    assert cache.bump_data_version.await_count == 1


def test_unknown_price_type_is_rejected() -> None:
    with pytest.raises(UnknownValueError):
        map_row({**BASE_ROW, PRICE_TYPE_COLUMN: "unknown"})


def test_user_cannot_supply_assistant_recommendations() -> None:
    with pytest.raises(ValidationError, match="listing_ids"):
        AssistantMessage(role="user", text="hi", listing_ids=[UUID(int=1)])


def test_override_model_and_complete_intent_chips() -> None:
    assert (
        SearchOverrides(models=["پژو"]).apply_to(SearchIntent()).vehicles[0].model
        == "پژو"
    )
    intent = SearchIntent(
        km_min=1000,
        km_max=50000,
        gearbox=Gearbox.AUTOMATIC,
        fuel=Fuel.PETROL,
        only_below_market=True,
    )
    chips = build_chips(intent, (VehicleTarget(MentionLevel.BRAND, "پژو"),), None)
    assert chips[0] == "پژو"
    assert "کارکرد از ۱ هزار" in chips
    assert "فقط ارزان‌تر از بازار" in chips


def test_audit_provider_constructs_service() -> None:
    assert get_audit_recorder(Mock()) is not None


def test_mileage_is_not_a_price() -> None:
    intent = parse_with_rules(
        "زیر 50 هزار کیلومتر زیر 60 هزار کیلومتر زیر 800 میلیون", []
    )
    assert intent.price_max == 800_000_000


@pytest.mark.db
async def test_scoped_facets_and_cached_response(
    api: AsyncClient, seeded_session: AsyncSession
) -> None:
    from enums import Category
    from repositories.catalog_repository import CatalogRepository
    from repositories.listing_repository import ListingRepository

    counts = await ListingRepository(seeded_session).count_by_category(Category.LIGHT)
    assert list(counts) == [Category.LIGHT]
    models = await CatalogRepository(seeded_session).list_top_models(Category.LIGHT, 5)
    assert models
    params = {
        "category": "light",
        "gearbox": "manual",
        "price_types": "lumpsum",
        "only_below": "true",
    }
    first = await api.get("/api/v1/facets", params=params)
    assert first.status_code == 200, first.text
    second = await api.get("/api/v1/facets", params=params)
    assert second.json() == first.json()
