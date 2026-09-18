"""Captures the frontend's JSON fixtures from THIS backend, served over the seeded
test database (no LLM, in-memory cache), into frontend/src/lib/api/__fixtures__/.

    ./.scripts/test-db.sh
    cd backend && uv run python -m tests.fixtures.capture_api_fixtures

The fixture CSV already blanks descriptions and rounds coordinates, so the captured
files hold no personal data; the one description is replaced by a short placeholder
so the listing page fixture still renders a seller text."""

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from core.config import get_settings
from db.session import get_session
from dependencies.providers import get_assistant_agent, get_cache, get_intent_agent
from ingest.pipeline import IngestPipeline
from main import create_app
from repositories.catalog_repository import CatalogRepository
from repositories.city_repository import CityRepository
from repositories.listing_repository import ListingRepository
from tests.conftest import FIXTURE_CSV
from tests.support import DictCache

OUTPUT_DIR = Path(__file__).resolve().parents[3] / "frontend/src/lib/api/__fixtures__"
DESCRIPTION_PLACEHOLDER = "توضیحات فروشنده (در فیکسچر کوتاه شده است)."
SEARCH_QUERY = "۲۰۶ تیپ ۲ تهران"
MODEL = "پژو 206"
MILLION = 1_000_000


async def _capture(http: AsyncClient) -> dict[str, Any]:
    search = await http.get(
        "/api/v1/search", params={"q": SEARCH_QUERY, "page_size": 14}
    )
    first = search.json()["items"][0]
    detail = (await http.get(f"/api/v1/listings/{first['id']}")).json()
    detail["description"] = DESCRIPTION_PLACEHOLDER
    similar = await http.get(
        f"/api/v1/listings/{first['id']}/similar", params={"limit": 3}
    )
    estimate = await http.post(
        "/api/v1/estimates",
        json={
            "category": "light",
            "trim": first["trim"],
            "year": first["year"],
            "km": first["km"],
            "insurance_months": first["insurance_months"],
            "asking_price": first["price"],
        },
    )
    assistant = await http.post(
        "/api/v1/assistant",
        json={"messages": [{"role": "user", "text": SEARCH_QUERY}], "compare_ids": []},
    )
    missing = "00000000-0000-8000-8000-000000000000"
    return {
        "search": search.json(),
        "listing": detail,
        "similar": similar.json(),
        "facets": (await http.get("/api/v1/facets")).json(),
        "model-stats": (await http.get(f"/api/v1/models/{MODEL}/stats")).json(),
        "suggest": (
            await http.get("/api/v1/catalog/suggest", params={"q": "پژو"})
        ).json(),
        "estimate": estimate.json(),
        "assistant": assistant.json(),
        "error-404": (await http.get(f"/api/v1/listings/{missing}")).json(),
        "error-422": (await http.get("/api/v1/search", params={"year": 1200})).json(),
    }


@asynccontextmanager
async def _seeded_session() -> AsyncIterator[tuple[AsyncSession, DictCache]]:
    engine = create_async_engine(get_settings().test_database_url, poolclass=NullPool)
    cache = DictCache()
    async with engine.connect() as connection:
        transaction = await connection.begin()
        async with AsyncSession(bind=connection, expire_on_commit=False) as session:
            pipeline = IngestPipeline(
                CityRepository(session),
                CatalogRepository(session),
                ListingRepository(session),
                cache,
            )
            await pipeline.run(FIXTURE_CSV)
            yield session, cache
        await transaction.rollback()
    await engine.dispose()


def _app_over(session: AsyncSession, cache: DictCache) -> AsyncClient:
    app = create_app()

    async def use_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = use_session
    app.dependency_overrides[get_cache] = lambda: cache
    app.dependency_overrides[get_intent_agent] = lambda: None
    app.dependency_overrides[get_assistant_agent] = lambda: None
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    return AsyncClient(transport=transport, base_url="http://test")


async def main() -> None:
    async with _seeded_session() as (session, cache):
        async with _app_over(session, cache) as http:
            captured = await _capture(http)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        for name, payload in captured.items():
            path = OUTPUT_DIR / f"{name}.json"
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
            print(path)


if __name__ == "__main__":
    asyncio.run(main())
