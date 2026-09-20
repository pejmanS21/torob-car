"""Stage 1 of search (spec §7.2): turn a SearchIntent's free-text mentions and city
names into catalog targets, city centroids and SQL guard rails."""

from dataclasses import dataclass

from core.text import normalize_persian, script_variants
from enums import MentionLevel
from ranking.types import RankingQuery, ResolvedCity, VehicleTarget
from ranking.weights import DEFAULT_WEIGHTS, RankingWeights
from repositories.catalog_repository import CatalogMatch, CatalogRepository
from repositories.city_repository import CityRepository
from repositories.listing_repository import CandidateFilter
from schemas.search import SearchIntent, VehicleMention
from services.intent_chips import build_chips

MIN_CATALOG_SIMILARITY = 0.6
CATALOG_MATCH_LIMIT = 1


@dataclass(frozen=True, slots=True)
class ResolvedIntent:
    query: RankingQuery
    filters: CandidateFilter
    chips: tuple[str, ...]


def _unique_tokens(*parts: str | None) -> str:
    tokens = normalize_persian(" ".join(part for part in parts if part)).split()
    return " ".join(dict.fromkeys(tokens))


def mention_queries(mention: VehicleMention) -> list[str]:
    """Most specific first. The second form drops the brand because the LLM often
    supplies the manufacturer («سایپا پراید») while Divar's string starts at «پراید»."""
    full = _unique_tokens(mention.brand, mention.model, mention.trim)
    without_brand = _unique_tokens(mention.model, mention.trim)
    return [query for query in dict.fromkeys((full, without_brand)) if query]


def infer_level(query: str, match: CatalogMatch) -> MentionLevel:
    """How specific the user was, judged by which catalog words they used — not by
    which field the parser happened to put them in."""
    tokens = set(query.split())
    if tokens <= set(match.brand.split()):
        return MentionLevel.BRAND
    if tokens <= set(match.model.split()):
        return MentionLevel.MODEL
    return MentionLevel.TRIM


def _to_target(query: str, match: CatalogMatch) -> VehicleTarget:
    level = infer_level(query, match)
    model = match.model if level is not MentionLevel.BRAND else None
    trim = match.trim if level is MentionLevel.TRIM else None
    return VehicleTarget(level, match.brand, model, trim)


class IntentResolver:
    def __init__(
        self,
        catalog: CatalogRepository,
        cities: CityRepository,
        weights: RankingWeights = DEFAULT_WEIGHTS,
    ) -> None:
        self._catalog = catalog
        self._cities = cities
        self._weights = weights

    async def resolve(self, intent: SearchIntent) -> ResolvedIntent:
        targets, leftovers = await self._resolve_vehicles(intent)
        text = normalize_persian(" ".join([*leftovers, intent.text or ""])) or None
        cities = await self._resolve_cities(intent.cities)
        query = RankingQuery(
            targets=targets,
            year_min=intent.year_min,
            year_max=intent.year_max,
            price_min=intent.price_min,
            price_max=intent.price_max,
            km_min=intent.km_min,
            km_max=intent.km_max,
            cities=cities,
            gearbox=intent.gearbox,
            fuel=intent.fuel,
            colors=tuple(intent.colors),
            has_text=text is not None,
            sort=intent.sort,
        )
        filters = self._guard_rails(intent, targets, text)
        return ResolvedIntent(query, filters, build_chips(intent, targets, text))

    async def _resolve_vehicles(
        self, intent: SearchIntent
    ) -> tuple[tuple[VehicleTarget, ...], list[str]]:
        targets: list[VehicleTarget] = []
        leftovers: list[str] = []
        for mention in intent.vehicles:
            target = await self._resolve_mention(mention, intent)
            if target is not None:
                targets.append(target)
            else:
                leftovers.extend(mention_queries(mention)[:1])
        return tuple(dict.fromkeys(targets)), leftovers

    async def _resolve_mention(
        self, mention: VehicleMention, intent: SearchIntent
    ) -> VehicleTarget | None:
        for query in mention_queries(mention):
            best = await self._best_match(query, intent)
            if best is not None:
                return best
        return None

    async def _best_match(
        self, query: str, intent: SearchIntent
    ) -> VehicleTarget | None:
        """The strongest catalog row across both scripts of the query. "g class" only
        reaches «بنز کلاس G جی 63» once «کلاس» is tried in place of "class"."""
        best_score = 0.0
        best: VehicleTarget | None = None
        for variant in script_variants(query):
            matches = await self._catalog.search(
                variant, intent.category, MIN_CATALOG_SIMILARITY, CATALOG_MATCH_LIMIT
            )
            if matches and matches[0].score > best_score:
                best_score = matches[0].score
                # How specific the mention was is judged from the user's own wording,
                # so the target keeps the original query, not the rewritten variant.
                best = _to_target(query, matches[0])
        return best

    async def _resolve_cities(self, names: list[str]) -> tuple[ResolvedCity, ...]:
        found = await self._cities.find_by_names(names) if names else []
        return tuple(ResolvedCity(city.name, city.lat, city.lng) for city in found)

    def _guard_rails(
        self, intent: SearchIntent, targets: tuple[VehicleTarget, ...], text: str | None
    ) -> CandidateFilter:
        weights = self._weights
        price_slack, km_slack = weights.price_tolerance, weights.km_tolerance
        return CandidateFilter(
            category=intent.category,
            brands=tuple(dict.fromkeys(target.brand for target in targets)),
            text=text,
            sources=tuple(intent.sources),
            price_types=tuple(intent.price_types),
            document_statuses=tuple(intent.document_statuses),
            only_below_market=intent.only_below_market,
            price_floor=intent.price_min
            and round(intent.price_min * (1 - price_slack)),
            price_ceiling=intent.price_max
            and round(intent.price_max * (1 + price_slack)),
            km_floor=intent.km_min and round(intent.km_min * (1 - km_slack)),
            km_ceiling=intent.km_max and round(intent.km_max * (1 + km_slack)),
            year_floor=intent.year_min and intent.year_min - weights.year_tolerance,
            year_ceiling=intent.year_max and intent.year_max + weights.year_tolerance,
        )
