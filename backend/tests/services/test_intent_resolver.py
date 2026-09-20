import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from enums import MentionLevel
from repositories.catalog_repository import CatalogMatch, CatalogRepository
from repositories.city_repository import CityRepository
from schemas.search import SearchIntent, VehicleMention
from services.intent_resolver import IntentResolver, infer_level, mention_queries

MATCH = CatalogMatch("پژو", "پژو 206", "پژو 206 تیپ ۲", 1.0)
MILLION = 1_000_000


@pytest.mark.parametrize(
    ("query", "level"),
    [
        ("پژو", MentionLevel.BRAND),
        ("206", MentionLevel.MODEL),
        ("پژو 206", MentionLevel.MODEL),
        ("206 تیپ 2", MentionLevel.TRIM),
        ("پژو 206 تیب 2", MentionLevel.TRIM),
    ],
)
def test_infer_level_follows_the_words_the_user_used(
    query: str, level: MentionLevel
) -> None:
    assert infer_level(query, MATCH) is level


def test_mention_queries_retry_without_the_brand() -> None:
    mention = VehicleMention(brand="سایپا", model="پراید")
    assert mention_queries(mention) == ["سایپا پراید", "پراید"]
    assert mention_queries(VehicleMention(brand="پژو", model="پژو ۲۰۶")) == ["پژو 206"]
    assert mention_queries(VehicleMention()) == []


@pytest.mark.db
async def test_resolve_builds_targets_cities_guard_rails_and_chips(
    seeded_session: AsyncSession,
) -> None:
    resolver = IntentResolver(
        CatalogRepository(seeded_session), CityRepository(seeded_session)
    )
    intent = SearchIntent(
        vehicles=[VehicleMention(brand="پژو", model="۲۰۶")],
        year_min=1398,
        year_max=1398,
        price_max=800 * MILLION,
        cities=["تهران"],
    )
    resolved = await resolver.resolve(intent)
    (target,) = resolved.query.targets
    assert (target.level, target.brand, target.model) == (
        MentionLevel.MODEL,
        "پژو",
        "پژو 206",
    )
    assert resolved.query.cities[0].name == "تهران"
    assert resolved.filters.brands == ("پژو",)
    assert resolved.filters.price_ceiling == 1_000 * MILLION
    assert (resolved.filters.year_floor, resolved.filters.year_ceiling) == (1393, 1403)
    assert resolved.chips == ("پژو 206", "مدل ۱۳۹۸", "زیر ۸۰۰ میلیون", "تهران")


@pytest.mark.db
async def test_unknown_vehicle_becomes_title_text(seeded_session: AsyncSession) -> None:
    resolver = IntentResolver(
        CatalogRepository(seeded_session), CityRepository(seeded_session)
    )
    intent = SearchIntent(vehicles=[VehicleMention(model="کامیون بنز")])
    resolved = await resolver.resolve(intent)
    assert resolved.query.targets == ()
    assert resolved.filters.text == "کامیون بنز" and resolved.query.has_text is True


class StubCatalog:
    """Scores «g class» the way Postgres does: the Latin spelling lands on the wrong
    Mercedes, and only the rewritten «g کلاس» reaches the real G Class."""

    def __init__(self) -> None:
        self.queries: list[str] = []

    async def search(
        self, query: str, category: object, min_similarity: float, limit: int
    ) -> list[CatalogMatch]:
        self.queries.append(query)
        by_query = {
            "g class": CatalogMatch(
                "مرسدس بنز", "مرسدس بنز c class", "مرسدس بنز C Class C200L", 0.75
            ),
            "g کلاس": CatalogMatch("بنز", "بنز کلاس", "بنز کلاس G جی 63", 1.0),
        }
        match = by_query.get(query)
        return [match] if match is not None and match.score >= min_similarity else []


class StubCities:
    async def find_by_names(self, names: list[str]) -> list[object]:
        return []


async def test_a_latin_query_reaches_the_catalog_row_written_in_persian() -> None:
    catalog = StubCatalog()
    resolver = IntentResolver(catalog, StubCities())  # type: ignore[arg-type]

    resolved = await resolver.resolve(
        SearchIntent(vehicles=[VehicleMention(model="g class")])
    )

    assert catalog.queries == ["g class", "g کلاس"]
    target = resolved.query.targets[0]
    assert (target.brand, target.trim) == ("بنز", "بنز کلاس G جی 63")
    # The SQL guard rail follows the winner, so the real G Class is not filtered out.
    assert resolved.filters.brands == ("بنز",)
