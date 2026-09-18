import uuid
from collections.abc import Collection
from dataclasses import dataclass

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.text import normalize_persian
from enums import Category
from models.listing import Listing
from models.vehicle_catalog import VehicleCatalog

type CatalogKey = tuple[Category, str]


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    category: Category
    brand: str
    model: str
    trim: str


@dataclass(frozen=True, slots=True)
class CatalogMatch:
    brand: str
    model: str
    trim: str
    score: float


@dataclass(frozen=True, slots=True)
class ModelCount:
    brand: str
    model: str
    listing_count: int


class CatalogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_entries(
        self, entries: Collection[CatalogEntry]
    ) -> dict[CatalogKey, uuid.UUID]:
        if entries:
            rows = [
                {
                    "category": entry.category,
                    "brand": entry.brand,
                    "model": entry.model,
                    "trim": entry.trim,
                    "trim_normalized": normalize_persian(entry.trim),
                }
                for entry in sorted(entries, key=lambda entry: entry.trim)
            ]
            statement = insert(VehicleCatalog).values(rows)
            await self._session.execute(
                statement.on_conflict_do_nothing(
                    constraint="uq_vehicle_catalog_category_trim"
                )
            )
        found = await self._session.execute(
            select(VehicleCatalog.category, VehicleCatalog.trim, VehicleCatalog.id)
        )
        return {(category, trim): catalog_id for category, trim, catalog_id in found}

    async def refresh_counts(self) -> None:
        per_entry = (
            select(
                Listing.catalog_id.label("catalog_id"),
                func.count().label("listing_count"),
            )
            .where(Listing.catalog_id.is_not(None))
            .group_by(Listing.catalog_id)
            .subquery()
        )
        await self._session.execute(
            update(VehicleCatalog)
            .where(VehicleCatalog.id == per_entry.c.catalog_id)
            .values(listing_count=per_entry.c.listing_count)
        )

    async def search(
        self, query: str, category: Category | None, min_similarity: float, limit: int
    ) -> list[CatalogMatch]:
        """Best catalog rows for a normalised free-text mention. `word_similarity`
        (not `similarity`) because «206» is a substring of «پژو 206 تیپ 2»."""
        score = func.word_similarity(query, VehicleCatalog.trim_normalized)
        statement = (
            select(
                VehicleCatalog.brand,
                VehicleCatalog.model,
                VehicleCatalog.trim,
                score.label("score"),
            )
            .where(score >= min_similarity)
            .order_by(score.desc(), VehicleCatalog.listing_count.desc())
            .limit(limit)
        )
        if category is not None:
            statement = statement.where(VehicleCatalog.category == category)
        found = await self._session.execute(statement)
        return [CatalogMatch(*row) for row in found]

    async def list_top_models(
        self, category: Category | None, limit: int
    ) -> list[ModelCount]:
        total = func.sum(VehicleCatalog.listing_count)
        statement = (
            select(VehicleCatalog.brand, VehicleCatalog.model, total.label("total"))
            .group_by(VehicleCatalog.brand, VehicleCatalog.model)
            .order_by(total.desc(), VehicleCatalog.model)
            .limit(limit)
        )
        if category is not None:
            statement = statement.where(VehicleCatalog.category == category)
        found = await self._session.execute(statement)
        return [ModelCount(brand, model, int(count)) for brand, model, count in found]
