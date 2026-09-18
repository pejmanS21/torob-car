from core.text import normalize_persian
from enums import Category
from repositories.catalog_repository import CatalogRepository
from schemas.catalog import CatalogSuggestion

SUGGEST_LIMIT = 10
# Looser than the resolver's 0.6: a type-ahead sees half-typed words.
MIN_SUGGEST_SIMILARITY = 0.3


class CatalogService:
    def __init__(self, catalog: CatalogRepository) -> None:
        self._catalog = catalog

    async def suggest(
        self, query: str | None, category: Category | None
    ) -> list[CatalogSuggestion]:
        rows = await self._catalog.suggest(
            normalize_persian(query or ""),
            category,
            MIN_SUGGEST_SIMILARITY,
            SUGGEST_LIMIT,
        )
        return [
            CatalogSuggestion(
                brand=row.brand,
                model=row.model,
                trim=row.trim,
                category=row.category,
                count=row.listing_count,
            )
            for row in rows
        ]
