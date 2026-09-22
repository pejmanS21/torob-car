"""Every FastAPI `Depends` provider — the single place where objects are wired."""

import time
from functools import lru_cache
from typing import Annotated

from fastapi import Cookie, Depends
from pydantic_ai import Agent
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from core.cache import Cache
from core.config import Settings, get_settings
from core.security import ACCESS_COOKIE, TokenClaims, decode_token
from db.session import get_session
from enums import TokenType
from errors import AdminReauthRequiredError, NotAuthenticatedError
from llm.assistant_agent import AssistantDeps, AssistantReply, build_assistant_agent
from llm.intent_agent import build_intent_agent
from llm.model_factory import build_model
from ranking.ranker import ListingRanker
from repositories.admin_audit_repository import AdminAuditRepository
from repositories.admin_user_repository import AdminUserRepository
from repositories.anonymous_chat_quota_repository import AnonymousChatQuotaRepository
from repositories.catalog_repository import CatalogRepository
from repositories.chat_repository import ChatRepository
from repositories.city_repository import CityRepository
from repositories.health_repository import HealthRepository
from repositories.listing_repository import ListingRepository
from repositories.price_alert_repository import PriceAlertRepository
from repositories.saved_listing_repository import SavedListingRepository
from repositories.user_repository import UserRepository
from schemas.auth import UserRead
from schemas.search import SearchIntent
from services.account_service import AccountService
from services.admin_audit_service import AdminAuditService
from services.admin_stats_service import AdminStatsService
from services.admin_user_service import AdminUserService
from services.anonymous_chat_limit import AnonymousChatLimit
from services.assistant_service import AssistantService
from services.audit_recorder import AuditRecorder
from services.auth_service import AuthService
from services.catalog_service import CatalogService
from services.chat_service import ChatService
from services.estimate_service import EstimateService
from services.facet_service import FacetService
from services.intent_resolver import IntentResolver
from services.listing_service import ListingService
from services.model_stats_service import ModelStatsService
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


@lru_cache
def get_assistant_agent() -> Agent[AssistantDeps, AssistantReply] | None:
    model = build_model(get_settings())
    return build_assistant_agent(model) if model is not None else None


CacheDep = Annotated[Cache, Depends(get_cache)]
AgentDep = Annotated[Agent[None, SearchIntent] | None, Depends(get_intent_agent)]
AssistantAgentDep = Annotated[
    Agent[AssistantDeps, AssistantReply] | None, Depends(get_assistant_agent)
]


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
    session: SessionDep,
    cache: CacheDep,
    settings: SettingsDep,
    parser: Annotated[QueryParser, Depends(get_query_parser)],
) -> FacetService:
    return FacetService(
        parser,
        IntentResolver(CatalogRepository(session), CityRepository(session)),
        ListingRepository(session),
        CatalogRepository(session),
        cache,
        settings.search_cache_ttl_seconds,
    )


def get_assistant_service(
    session: SessionDep,
    settings: SettingsDep,
    search: Annotated[SearchService, Depends(get_search_service)],
    agent: AssistantAgentDep,
) -> AssistantService:
    return AssistantService(
        agent,
        search,
        ListingRepository(session),
        settings.assistant_timeout_seconds,
    )


def get_chat_service(
    session: SessionDep,
    settings: SettingsDep,
    assistant: Annotated[AssistantService, Depends(get_assistant_service)],
) -> ChatService:
    return ChatService(
        assistant,
        ChatRepository(session),
        ListingRepository(session),
        AnonymousChatLimit(AnonymousChatQuotaRepository(session), settings),
    )


def get_estimate_service(
    session: SessionDep,
    search: Annotated[SearchService, Depends(get_search_service)],
) -> EstimateService:
    return EstimateService(
        CatalogRepository(session), ListingRepository(session), search
    )


def get_model_stats_service(session: SessionDep) -> ModelStatsService:
    return ModelStatsService(CatalogRepository(session), ListingRepository(session))


def get_catalog_service(session: SessionDep) -> CatalogService:
    return CatalogService(CatalogRepository(session))


def get_health_repository(session: SessionDep) -> HealthRepository:
    return HealthRepository(session)


def get_auth_service(session: SessionDep, settings: SettingsDep) -> AuthService:
    return AuthService(UserRepository(session), settings)


def get_account_service(session: SessionDep) -> AccountService:
    return AccountService(
        SavedListingRepository(session),
        PriceAlertRepository(session),
        ListingRepository(session),
    )


def get_current_user(
    settings: SettingsDep,
    access_token: Annotated[str | None, Cookie(alias=ACCESS_COOKIE)] = None,
) -> TokenClaims:
    """Trusts the signed token alone — no database hit. A disabled user is therefore
    locked out at their next refresh (≤ 15 min), not instantly; see `require_admin`."""
    if access_token is None:
        raise NotAuthenticatedError()
    secret = settings.jwt_secret.get_secret_value()
    return decode_token(access_token, secret, TokenType.ACCESS)


CurrentUserDep = Annotated[TokenClaims, Depends(get_current_user)]


def get_optional_user(
    settings: SettingsDep,
    access_token: Annotated[str | None, Cookie(alias=ACCESS_COOKIE)] = None,
) -> TokenClaims | None:
    """For routes anonymous visitors may use. No cookie means anonymous; a cookie that
    is present but invalid still raises, so an expired session gets its 401 and the
    client's refresh-and-replay runs — it never degrades silently to anonymous."""
    if access_token is None:
        return None
    secret = settings.jwt_secret.get_secret_value()
    return decode_token(access_token, secret, TokenType.ACCESS)


OptionalUserDep = Annotated[TokenClaims | None, Depends(get_optional_user)]


def _require_fresh_enough(auth_at: int, window_minutes: int) -> None:
    """`auth_at` is stamped only by a real password entry — a refresh carries the old
    value through. So this measures time since the human was last present, not since
    the session was last active."""
    if int(time.time()) - auth_at > window_minutes * 60:
        raise AdminReauthRequiredError()


async def require_admin(
    current: CurrentUserDep,
    settings: SettingsDep,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserRead:
    _require_fresh_enough(current.auth_at, settings.admin_session_minutes)
    return await service.require_admin(current.user_id)


async def require_fresh_admin(
    current: CurrentUserDep,
    settings: SettingsDep,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserRead:
    _require_fresh_enough(current.auth_at, settings.admin_reauth_minutes)
    return await service.require_admin(current.user_id)


# Only the destructive routes need the actor injected; reads are covered by the
# router-level guard alone, so there is deliberately no plain `AdminDep`.
FreshAdminDep = Annotated[UserRead, Depends(require_fresh_admin)]


def get_audit_recorder(session: SessionDep) -> AuditRecorder:
    return AuditRecorder(AdminAuditRepository(session))


def get_admin_user_service(
    session: SessionDep, settings: SettingsDep
) -> AdminUserService:
    return AdminUserService(
        UserRepository(session),
        AdminUserRepository(session),
        AuditRecorder(AdminAuditRepository(session)),
        settings,
    )


def get_admin_audit_service(session: SessionDep) -> AdminAuditService:
    return AdminAuditService(AdminAuditRepository(session))


def get_admin_stats_service(session: SessionDep) -> AdminStatsService:
    return AdminStatsService(
        AdminUserRepository(session),
        ListingRepository(session),
        AuditRecorder(AdminAuditRepository(session)),
    )
