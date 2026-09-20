"""Filter-panel counts, scoped to the current search: each option says how many
listings it would give within everything else the user asked for."""

import hashlib
import json
from dataclasses import replace

from core.cache import Cache
from enums import Category, FacetDimension
from repositories.catalog_repository import CatalogRepository
from repositories.listing_repository import FacetScope, ListingRepository
from schemas.facets import (
    AppliedFilters,
    FacetCount,
    FacetRanges,
    Facets,
    ModelFacet,
)
from schemas.search import SearchIntent, SearchOverrides
from services.intent_resolver import IntentResolver, ResolvedIntent
from services.query_parser import QueryParser

TOP_MODELS = 60
TOP_CITIES = 60
ALL_OPTIONS = 100  # categories, sources and gearboxes are a handful each


def scope_of(intent: SearchIntent, resolved: ResolvedIntent) -> FacetScope:
    """The search as yes/no conditions. The resolver's guard rails are widened by the
    ranking tolerances; a count needs the bounds exactly as the user stated them."""
    exact = replace(
        resolved.filters,
        price_floor=intent.price_min,
        price_ceiling=intent.price_max,
        km_floor=intent.km_min,
        km_ceiling=intent.km_max,
        year_floor=intent.year_min,
        year_ceiling=intent.year_max,
    )
    models = tuple(
        dict.fromkeys(t.model for t in resolved.query.targets if t.model is not None)
    )
    cities = tuple(city.name for city in resolved.query.cities)
    return FacetScope(exact, models, cities, intent.gearbox)


def applied_of(intent: SearchIntent, scope: FacetScope) -> AppliedFilters:
    return AppliedFilters(
        category=intent.category,
        models=list(scope.models),
        cities=list(scope.cities),
        gearbox=intent.gearbox,
        sources=intent.sources,
        price_types=intent.price_types,
        document_statuses=intent.document_statuses,
        price_min=intent.price_min,
        price_max=intent.price_max,
        km_min=intent.km_min,
        km_max=intent.km_max,
        year_min=intent.year_min,
        year_max=intent.year_max,
        only_below_market=intent.only_below_market,
    )


class FacetService:
    def __init__(
        self,
        parser: QueryParser,
        resolver: IntentResolver,
        listings: ListingRepository,
        catalog: CatalogRepository,
        cache: Cache,
        cache_ttl_seconds: int,
    ) -> None:
        self._parser = parser
        self._resolver = resolver
        self._listings = listings
        self._catalog = catalog
        self._cache = cache
        self._cache_ttl_seconds = cache_ttl_seconds

    async def get_facets(self, query: str | None, overrides: SearchOverrides) -> Facets:
        parsed = await self._parser.parse(query or "")
        intent = overrides.apply_to(parsed.intent)
        key = await self._cache_key(intent)
        cached = await self._cache.get_json(key)
        if cached is not None:
            return Facets.model_validate(cached)
        facets = await self._build(intent)
        payload = facets.model_dump(mode="json")
        await self._cache.set_json(key, payload, self._cache_ttl_seconds)
        return facets

    async def _build(self, intent: SearchIntent) -> Facets:
        scope = scope_of(intent, await self._resolver.resolve(intent))
        count = self._listings.count_facet
        categories = await count(scope, FacetDimension.CATEGORY, ALL_OPTIONS)
        models = await count(scope, FacetDimension.MODEL, TOP_MODELS)
        cities = await count(scope, FacetDimension.CITY, TOP_CITIES)
        sources = await count(scope, FacetDimension.SOURCE, ALL_OPTIONS)
        gearboxes = await count(scope, FacetDimension.GEARBOX, ALL_OPTIONS)
        ranges = await self._listings.facet_ranges(scope)
        return Facets(
            categories={Category(row.value): row.count for row in categories},
            models=[
                ModelFacet(brand=row.brand or "", model=row.value, count=row.count)
                for row in models
            ],
            cities=[FacetCount(value=row.value, count=row.count) for row in cities],
            sources=[FacetCount(value=row.value, count=row.count) for row in sources],
            gearboxes=[
                FacetCount(value=row.value, count=row.count) for row in gearboxes
            ],
            ranges=FacetRanges(
                price_min=ranges.price_min,
                price_max=ranges.price_max,
                km_min=ranges.km_min,
                km_max=ranges.km_max,
                year_min=ranges.year_min,
                year_max=ranges.year_max,
            ),
            applied=applied_of(intent, scope),
            model_count=await self._catalog.count_models(intent.category),
            data_as_of=await self._listings.newest_fetched_at(),
        )

    async def _cache_key(self, intent: SearchIntent) -> str:
        version = await self._cache.get_data_version()
        canonical = json.dumps(
            intent.model_dump(mode="json"), sort_keys=True, ensure_ascii=False
        )
        return f"facets:{version}:{hashlib.sha256(canonical.encode()).hexdigest()}"
