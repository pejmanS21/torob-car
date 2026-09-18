"""SearchService in isolation: every collaborator is a stub (CLAUDE.md §8)."""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from enums import Category, EstimateBasis, ParsedBy
from errors import InvalidSearchError, ListingNotFoundError
from ranking.ranker import ListingRanker
from ranking.types import Candidate, RankingQuery
from repositories.listing_repository import CandidateFilter
from schemas.search import SearchIntent, SearchOverrides
from services.intent_resolver import ResolvedIntent
from services.listing_service import MAX_BATCH_IDS, ListingService
from services.query_parser import ParsedQuery
from services.search_service import SearchService
from tests.support import DictCache

NOW = datetime(2026, 9, 17, 20, 0, tzinfo=UTC)
IDS = [uuid.UUID(int=number) for number in range(1, 4)]


def make_listing(listing_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=listing_id,
        token=f"tok{listing_id.int}",
        title="پژو ۲۰۶",
        category=Category.LIGHT,
        catalog=None,
        city=SimpleNamespace(name="تهران"),
        year=1398,
        km=60_000,
        price=800_000_000,
        district=None,
        thumbnail_urls=[],
        image_urls=[],
        posted_at=NOW,
        est_price=None,
        diff_pct=None,
        deal_score=None,
        est_basis=EstimateBasis.NONE,
    )


class StubParser:
    async def parse(self, text: str) -> ParsedQuery:
        return ParsedQuery(SearchIntent(), ParsedBy.RULES)


class StubResolver:
    async def resolve(self, intent: SearchIntent) -> ResolvedIntent:
        return ResolvedIntent(RankingQuery(), CandidateFilter(), ("چیپ",))


class StubListings:
    def __init__(self) -> None:
        self.candidate_queries = 0
        self.last_filters: CandidateFilter | None = None

    async def find_candidates(
        self, filters: CandidateFilter, limit: int
    ) -> list[Candidate]:
        self.candidate_queries += 1
        self.last_filters = filters
        scores = (90, 50, 70)
        return [
            Candidate(id=listing_id, deal_score=score, posted_at=NOW)
            for listing_id, score in zip(IDS, scores, strict=True)
        ]

    async def newest_fetched_at(self) -> datetime:
        return NOW

    async def get_by_ids(self, listing_ids: list[uuid.UUID]) -> list[SimpleNamespace]:
        return [make_listing(listing_id) for listing_id in listing_ids]

    async def get_by_id(self, listing_id: uuid.UUID) -> None:
        return None


def make_service(listings: StubListings, cache: DictCache) -> SearchService:
    return SearchService(
        StubParser(), StubResolver(), listings, ListingRanker(), cache, 60
    )


async def test_search_ranks_pages_and_reports_totals() -> None:
    service = make_service(StubListings(), DictCache())
    response = await service.search(None, SearchOverrides(), page=1, page_size=2)
    assert (response.total, response.exact_count) == (3, 3)
    assert [item.id for item in response.items] == [IDS[0], IDS[2]]  # deal 90, 70
    assert response.intent.chips == ["چیپ"]


async def test_second_page_reuses_the_cached_ranking() -> None:
    listings, cache = StubListings(), DictCache()
    service = make_service(listings, cache)
    await service.search(None, SearchOverrides(), page=1, page_size=2)
    second = await service.search(None, SearchOverrides(), page=2, page_size=2)
    assert listings.candidate_queries == 1
    assert [item.id for item in second.items] == [IDS[1]]


async def test_a_new_data_version_invalidates_the_cached_ranking() -> None:
    listings, cache = StubListings(), DictCache()
    service = make_service(listings, cache)
    await service.search(None, SearchOverrides(), page=1, page_size=2)
    await cache.bump_data_version()
    await service.search(None, SearchOverrides(), page=1, page_size=2)
    assert listings.candidate_queries == 2


async def test_paging_past_the_result_cap_is_rejected() -> None:
    service = make_service(StubListings(), DictCache())
    with pytest.raises(InvalidSearchError):
        await service.search(None, SearchOverrides(), page=11, page_size=50)


async def test_similar_search_excludes_the_listing_itself() -> None:
    listings = StubListings()
    service = make_service(listings, DictCache())
    await service.rank(SearchIntent(), exclude_id=IDS[0])
    assert listings.last_filters.exclude_id == IDS[0]


async def test_listing_service_guards_missing_listings_and_batch_size() -> None:
    listings = StubListings()
    service = ListingService(listings, make_service(listings, DictCache()))
    with pytest.raises(ListingNotFoundError):
        await service.get_detail(IDS[0])
    with pytest.raises(InvalidSearchError):
        await service.get_many([uuid.uuid4() for _ in range(MAX_BATCH_IDS + 1)])
