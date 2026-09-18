"""Search orchestration (spec §7): parse → resolve → candidates → rank → cache."""

import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from core.cache import Cache
from enums import ParsedBy
from errors import InvalidSearchError
from ranking.ranker import ListingRanker
from ranking.types import RankedListing
from repositories.listing_repository import ListingRepository
from schemas.listing import ListingCard
from schemas.search import IntentRead, SearchIntent, SearchOverrides, SearchResponse
from services.intent_resolver import IntentResolver
from services.listing_views import to_card
from services.query_parser import QueryParser

logger = logging.getLogger(__name__)

MAX_CANDIDATES = 5_000
# ponytail: only the top 500 are cached and pageable; re-rank on demand if anyone
# ever pages deeper.
MAX_RESULTS = 500
MILLISECONDS = 1_000


@dataclass(frozen=True, slots=True)
class RankedSearch:
    chips: tuple[str, ...]
    results: tuple[RankedListing, ...]


def _to_payload(search: RankedSearch) -> dict[str, object]:
    rows = [
        [str(item.id), item.rank, item.match, item.is_exact, list(item.labels)]
        for item in search.results
    ]
    return {"chips": list(search.chips), "results": rows}


def _from_payload(payload: dict) -> RankedSearch:
    results = tuple(
        RankedListing(uuid.UUID(listing_id), rank, match, is_exact, tuple(labels))
        for listing_id, rank, match, is_exact, labels in payload["results"]
    )
    return RankedSearch(tuple(payload["chips"]), results)


class SearchService:
    def __init__(
        self,
        parser: QueryParser,
        resolver: IntentResolver,
        listings: ListingRepository,
        ranker: ListingRanker,
        cache: Cache,
        cache_ttl_seconds: int,
    ) -> None:
        self._parser = parser
        self._resolver = resolver
        self._listings = listings
        self._ranker = ranker
        self._cache = cache
        self._cache_ttl_seconds = cache_ttl_seconds

    async def search(
        self, query: str | None, overrides: SearchOverrides, page: int, page_size: int
    ) -> SearchResponse:
        started = time.perf_counter()
        parsed = await self._parser.parse(query or "")
        intent = overrides.apply_to(parsed.intent)
        ranked, cache_hit = await self.rank(intent)
        items = await self.page_of(ranked.results, page, page_size)
        self._log(parsed.parsed_by, cache_hit, len(ranked.results), started)
        return SearchResponse(
            intent=IntentRead(**intent.model_dump(), chips=list(ranked.chips)),
            parsed_by=parsed.parsed_by,
            total=len(ranked.results),
            exact_count=sum(item.is_exact for item in ranked.results),
            page=page,
            page_size=page_size,
            items=items,
        )

    async def rank(
        self, intent: SearchIntent, exclude_id: uuid.UUID | None = None
    ) -> tuple[RankedSearch, bool]:
        key = await self._cache_key(intent, exclude_id)
        cached = await self._cache.get_json(key)
        if cached is not None:
            return _from_payload(cached), True
        resolved = await self._resolver.resolve(intent)
        filters = replace(resolved.filters, exclude_id=exclude_id)
        candidates = await self._listings.find_candidates(filters, MAX_CANDIDATES)
        now = await self._listings.newest_fetched_at() or datetime.now(UTC)
        results = self._ranker.rank(resolved.query, candidates, now)[:MAX_RESULTS]
        search = RankedSearch(resolved.chips, tuple(results))
        await self._cache.set_json(key, _to_payload(search), self._cache_ttl_seconds)
        return search, False

    async def page_of(
        self, results: tuple[RankedListing, ...], page: int, page_size: int
    ) -> list[ListingCard]:
        start = (page - 1) * page_size
        if start >= MAX_RESULTS:
            raise InvalidSearchError(
                f"Only the first {MAX_RESULTS} results can be paged",
                {"page": page, "page_size": page_size},
            )
        window = results[start : start + page_size]
        listings = await self._listings.get_by_ids([item.id for item in window])
        ranked_by_id = {item.id: item for item in window}
        return [to_card(listing, ranked_by_id[listing.id]) for listing in listings]

    async def _cache_key(
        self, intent: SearchIntent, exclude_id: uuid.UUID | None
    ) -> str:
        version = await self._cache.get_data_version()
        canonical = json.dumps(
            {"intent": intent.model_dump(mode="json"), "exclude": str(exclude_id)},
            sort_keys=True,
            ensure_ascii=False,
        )
        return f"search:{version}:{hashlib.sha256(canonical.encode()).hexdigest()}"

    @staticmethod
    def _log(parsed_by: ParsedBy, cache_hit: bool, total: int, started: float) -> None:
        fields = {
            "parsed_by": parsed_by.value,
            "cache_hit": cache_hit,
            "total": total,
            "duration_ms": round((time.perf_counter() - started) * MILLISECONDS),
        }
        logger.info("search", extra={"fields": fields})
