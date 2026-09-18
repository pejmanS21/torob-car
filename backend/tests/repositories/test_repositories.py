from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from enums import Category
from ingest.pipeline import IngestPipeline
from repositories.catalog_repository import CatalogRepository
from repositories.city_repository import CityRepository
from repositories.listing_repository import CandidateFilter, ListingRepository
from tests.support import DictCache

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


async def test_second_ingest_of_the_same_file_changes_nothing(
    seeded_session: AsyncSession, cache: DictCache
) -> None:
    fixture_csv = (
        Path(__file__).resolve().parents[1] / "fixtures" / "listings_sample.csv"
    )
    assert fixture_csv.exists()

    # Record initial state after seeded_session fixture has already run once
    listings_repo = ListingRepository(seeded_session)
    cities_repo = CityRepository(seeded_session)
    catalog_repo = CatalogRepository(seeded_session)

    initial_listing_count = await listings_repo.count()
    assert initial_listing_count == 617

    initial_cities = len(await cities_repo.list_names())
    assert initial_cities > 0

    # Count catalog entries by querying top models with a high limit
    initial_catalog_models = await catalog_repo.list_top_models(None, 10_000)
    initial_catalog_count = len(initial_catalog_models)
    assert initial_catalog_count > 0

    # Run the pipeline a second time with the same file
    pipeline = IngestPipeline(cities_repo, catalog_repo, listings_repo, cache)
    report = await pipeline.run(fixture_csv)

    # Verify idempotency: counts unchanged, full re-match, no rejects
    assert await listings_repo.count() == initial_listing_count
    assert await listings_repo.count() == 617
    assert len(await cities_repo.list_names()) == initial_cities
    final_catalog_models = await catalog_repo.list_top_models(None, 10_000)
    assert len(final_catalog_models) == initial_catalog_count

    # Verify the re-ingest report
    assert report.rows_read == 617
    assert report.rows_upserted == 617
    assert report.rows_rejected == 0
    assert report.data_version == 2
