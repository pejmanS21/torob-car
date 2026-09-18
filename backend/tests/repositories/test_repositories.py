import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from enums import Category
from repositories.catalog_repository import CatalogRepository
from repositories.city_repository import CityRepository
from repositories.listing_repository import CandidateFilter, ListingRepository

pytestmark = pytest.mark.db
MILLION = 1_000_000


async def test_ingest_is_idempotent_and_fills_every_table(
    seeded_session: AsyncSession,
) -> None:
    listings = ListingRepository(seeded_session)
    assert await listings.count() == 617
    counts = await listings.count_by_category()
    assert counts[Category.LIGHT] == 420 and counts[Category.MOTORCYCLE] == 120
    tehran = (await CityRepository(seeded_session).find_by_names(["تهران"]))[0]
    assert 35.4 < tehran.lat < 36.0 and 51.0 < tehran.lng < 51.8  # median centroid
    assert tehran.listing_count > 50


@pytest.mark.parametrize(
    ("query", "brand", "model"),
    [
        ("206", "پژو", "پژو 206"),
        ("پژو 206 تیپ 2", "پژو", "پژو 206"),
        ("پژو 206 تیب 2", "پژو", "پژو 206"),  # typo still resolves
        ("پراید", "پراید", "پراید صندوق دار"),  # «صندوق‌دار» stays one word
        ("سمند", "سمند", "سمند lx"),
    ],
)
async def test_catalog_search_finds_the_vehicle(
    seeded_session: AsyncSession, query: str, brand: str, model: str
) -> None:
    matches = await CatalogRepository(seeded_session).search(query, None, 0.6, 1)
    assert (matches[0].brand, matches[0].model) == (brand, model)


async def test_catalog_search_returns_nothing_for_an_unknown_vehicle(
    seeded_session: AsyncSession,
) -> None:
    assert await CatalogRepository(seeded_session).search("بوگاتی", None, 0.6, 1) == []


async def test_candidates_respect_brand_and_guard_rails(
    seeded_session: AsyncSession,
) -> None:
    filters = CandidateFilter(
        brands=("پژو",),
        price_ceiling=1_000 * MILLION,
        year_floor=1393,
        year_ceiling=1403,
    )
    candidates = await ListingRepository(seeded_session).find_candidates(filters, 5_000)
    assert candidates
    assert {candidate.brand for candidate in candidates} == {"پژو"}
    assert all(c.price is None or c.price <= 1_000 * MILLION for c in candidates)
    assert all(c.year is None or 1393 <= c.year <= 1403 for c in candidates)
    assert all(c.lat is not None for c in candidates)  # falls back to the centroid


async def test_text_candidates_carry_a_similarity_score(
    seeded_session: AsyncSession,
) -> None:
    filters = CandidateFilter(category=Category.HEAVY, text="کامیون")
    candidates = await ListingRepository(seeded_session).find_candidates(filters, 50)
    assert candidates and all(c.text_similarity >= 0.3 for c in candidates)


async def test_suspect_prices_are_hidden_from_candidates(
    seeded_session: AsyncSession,
) -> None:
    repository = ListingRepository(seeded_session)
    everything = await repository.find_candidates(CandidateFilter(), 5_000)
    hidden = sum(candidate.price is None for candidate in everything)
    cheap_only = CandidateFilter(price_ceiling=50 * MILLION, category=Category.LIGHT)
    cheap = await repository.find_candidates(cheap_only, 5_000)
    assert hidden > 0
    assert all(c.price is None or c.price <= 50 * MILLION for c in cheap)
