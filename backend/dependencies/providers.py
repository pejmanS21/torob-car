"""Every FastAPI `Depends` provider — the single place where objects are wired."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from pydantic_ai import Agent
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from core.cache import Cache
from core.config import Settings, get_settings
from db.session import get_session
from llm.intent_agent import build_intent_agent
from llm.model_factory import build_model
from ranking.ranker import ListingRanker
from repositories.catalog_repository import CatalogRepository
from repositories.city_repository import CityRepository
from repositories.health_repository import HealthRepository
from repositories.listing_repository import ListingRepository
from schemas.search import SearchIntent
from services.facet_service import FacetService
from services.intent_resolver import IntentResolver
from services.listing_service import ListingService
from services.query_parser import QueryParser
from services.search_service import SearchService

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


@lru_cache
def get_cache() -> Cache:
    client = Redis.from_url(get_settings().redis_url, decode_responses=True)
    return Cache(client)


@lru_cache
def get_intent_agent() -> Agent[None, SearchIntent] | None:
    model = build_model(get_settings())
    return build_intent_agent(model) if model is not None else None


CacheDep = Annotated[Cache, Depends(get_cache)]
AgentDep = Annotated[Agent[None, SearchIntent] | None, Depends(get_intent_agent)]


def get_query_parser(
    session: SessionDep, cache: CacheDep, agent: AgentDep, settings: SettingsDep
) -> QueryParser:
    return QueryParser(
        agent,
        CityRepository(session),
        cache,
        settings.llm_timeout_seconds,
        settings.intent_cache_ttl_seconds,
    )


def get_search_service(
    session: SessionDep,
    cache: CacheDep,
    settings: SettingsDep,
    parser: Annotated[QueryParser, Depends(get_query_parser)],
) -> SearchService:
    resolver = IntentResolver(CatalogRepository(session), CityRepository(session))
    return SearchService(
        parser,
        resolver,
        ListingRepository(session),
        ListingRanker(),
        cache,
        settings.search_cache_ttl_seconds,
    )


def get_listing_service(
    session: SessionDep,
    search: Annotated[SearchService, Depends(get_search_service)],
) -> ListingService:
    return ListingService(ListingRepository(session), search)


def get_facet_service(
    session: SessionDep, cache: CacheDep, settings: SettingsDep
) -> FacetService:
    return FacetService(
        ListingRepository(session),
        CatalogRepository(session),
        cache,
        settings.search_cache_ttl_seconds,
    )


def get_health_repository(session: SessionDep) -> HealthRepository:
    return HealthRepository(session)
