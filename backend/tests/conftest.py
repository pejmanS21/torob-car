import json
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic_ai import (
    ModelMessage,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    models,
)
from pydantic_ai.models.function import (
    AgentInfo,
    DeltaToolCall,
    DeltaToolCalls,
    FunctionModel,
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from core.config import get_settings
from db.session import get_session
from dependencies.providers import get_assistant_agent, get_cache, get_intent_agent
from ingest.pipeline import IngestPipeline
from llm.assistant_agent import build_assistant_agent
from main import create_app
from repositories.catalog_repository import CatalogRepository
from repositories.city_repository import CityRepository
from repositories.listing_repository import ListingRepository
from tests.support import DictCache, fast_auth_settings

models.ALLOW_MODEL_REQUESTS = False  # tests must never reach a real LLM


def _scripted_assistant(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    """A two-turn stand-in for the real agent: search once, then answer with the ids
    that search returned. The assistant has no canned reply any more, so tests need a
    model that behaves like one — offline, and deterministic."""
    returned = [
        part.content
        for message in messages
        for part in message.parts
        if isinstance(part, ToolReturnPart)
    ]
    if not returned:
        return ModelResponse(
            parts=[ToolCallPart("search_listings", {"intent": {"text": "۲۰۶"}})]
        )
    listing_ids = [listing["id"] for listing in returned[0]["listings"][:3]]
    reply = {"text": "این‌ها به‌صرفه‌ترین‌ها هستند.", "listing_ids": listing_ids}
    return ModelResponse(parts=[TextPart(json.dumps(reply, ensure_ascii=False))])


async def _streamed_assistant(
    messages: list[ModelMessage], info: AgentInfo
) -> AsyncIterator[str | DeltaToolCalls]:
    for part in _scripted_assistant(messages, info).parts:
        if isinstance(part, ToolCallPart):
            yield {
                0: DeltaToolCall(name=part.tool_name, json_args=json.dumps(part.args))
            }
        elif isinstance(part, TextPart):
            for offset in range(0, len(part.content), 10):
                yield part.content[offset : offset + 10]


BACKEND_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_CSV = BACKEND_ROOT / "tests" / "fixtures" / "listings_sample.csv"


@pytest.fixture(scope="session")
def migrated_database_url() -> str:
    """Runs the real Alembic migrations once against the throwaway test database
    (start it with `docker compose -f .docker/compose.test.yml up -d`)."""
    url = get_settings().test_database_url
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "db" / "migrations"))
    config.attributes["database_url"] = url
    command.upgrade(config, "head")
    return url


@pytest.fixture
async def session(migrated_database_url: str) -> AsyncIterator[AsyncSession]:
    """A session inside one outer transaction that is always rolled back."""
    engine = create_async_engine(migrated_database_url, poolclass=NullPool)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        async with AsyncSession(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        ) as db_session:
            yield db_session
        await transaction.rollback()
    await engine.dispose()


@pytest.fixture
def cache() -> DictCache:
    return DictCache()


@pytest.fixture
async def seeded_session(session: AsyncSession, cache: DictCache) -> AsyncSession:
    """The ~600-row fixture CSV loaded through the real ingest pipeline."""
    pipeline = IngestPipeline(
        CityRepository(session),
        CatalogRepository(session),
        ListingRepository(session),
        cache,
    )
    await pipeline.run(FIXTURE_CSV)
    return session


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


@pytest.fixture
async def api(
    app: FastAPI, seeded_session: AsyncSession, cache: DictCache
) -> AsyncIterator[AsyncClient]:
    """HTTP client wired to the seeded test database and an in-memory cache. Search
    runs on the rules parser (no intent agent); the assistant, which has no rules path
    at all, gets the scripted model above. Neither reaches a provider."""

    async def use_seeded_session() -> AsyncIterator[AsyncSession]:
        yield seeded_session

    app.dependency_overrides[get_session] = use_seeded_session
    app.dependency_overrides[get_cache] = lambda: cache
    app.dependency_overrides[get_intent_agent] = lambda: None
    app.dependency_overrides[get_assistant_agent] = lambda: build_assistant_agent(
        FunctionModel(_scripted_assistant, stream_function=_streamed_assistant)
    )
    app.dependency_overrides[get_settings] = fast_auth_settings
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
