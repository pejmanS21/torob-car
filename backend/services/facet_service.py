from core.cache import Cache
from enums import Category
from repositories.catalog_repository import CatalogRepository
from repositories.city_repository import CityRepository
from repositories.listing_repository import ListingRepository
from schemas.facets import FacetCount, Facets, ModelFacet

TOP_MODELS = 60
TOP_CITIES = 60


class FacetService:
    def __init__(
        self,
        listings: ListingRepository,
        catalog: CatalogRepository,
        cities: CityRepository,
        cache: Cache,
        cache_ttl_seconds: int,
    ) -> None:
        self._listings = listings
        self._catalog = catalog
        self._cities = cities
        self._cache = cache
        self._cache_ttl_seconds = cache_ttl_seconds

    async def get_facets(self, category: Category | None) -> Facets:
        version = await self._cache.get_data_version()
        key = f"facets:{version}:{category.value if category else 'all'}"
        cached = await self._cache.get_json(key)
        if cached is not None:
            return Facets.model_validate(cached)
        facets = await self._build(category)
        payload = facets.model_dump(mode="json")
        await self._cache.set_json(key, payload, self._cache_ttl_seconds)
        return facets

    async def _build(self, category: Category | None) -> Facets:
        models = await self._catalog.list_top_models(category, TOP_MODELS)
        cities = await self._cities.list_top(TOP_CITIES)
        return Facets(
            categories=await self._listings.count_by_category(),
            models=[
                ModelFacet(brand=item.brand, model=item.model, count=item.listing_count)
                for item in models
            ],
            cities=[
                FacetCount(value=city.name, count=city.listing_count) for city in cities
            ],
        )
