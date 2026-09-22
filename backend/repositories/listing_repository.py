import uuid
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from typing import Any, cast

from sqlalchemy import (
    ColumnElement,
    Select,
    case,
    func,
    literal,
    null,
    or_,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from enums import (
    Category,
    DocumentStatus,
    FacetDimension,
    Gearbox,
    PriceType,
    Source,
)
from models.city import City
from models.listing import Listing
from models.vehicle_catalog import VehicleCatalog
from ranking.estimator import Estimate, EstimatorInput
from ranking.model_stats import ModelRow
from ranking.types import Candidate
from ranking.weights import CHEAP_DIFF_PCT

# asyncpg allows 32,767 bind parameters per statement; a listing row has ~35 columns.
UPSERT_BATCH_SIZE = 500
MIN_TEXT_SIMILARITY = 0.3
_IMMUTABLE_COLUMNS = frozenset({"id", "token"})


@dataclass(frozen=True, slots=True)
class CandidateFilter:
    """Absolute bounds, already widened by the ranking tolerances (spec §7.3). A
    bound of None means the user did not state that criterion. NULL column values
    always pass: the ranker scores them as unknown."""

    category: Category | None = None
    brands: tuple[str, ...] = ()
    text: str | None = None
    sources: tuple[Source, ...] = ()
    # Stated on a minority of ads, so these keep rows whose value is NULL: filtering on
    # them narrows the ads that answered, it never hides the ads that stayed silent.
    price_types: tuple[PriceType, ...] = ()
    document_statuses: tuple[DocumentStatus, ...] = ()
    only_below_market: bool = False
    price_floor: int | None = None
    price_ceiling: int | None = None
    km_floor: int | None = None
    km_ceiling: int | None = None
    year_floor: int | None = None
    year_ceiling: int | None = None
    exclude_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class FacetScope:
    """What the search asked for, as yes/no conditions. Ranking treats model, city and
    gearbox softly (near-misses stay in); a count cannot, so here they are hard and
    `filters` carries the exact bounds, not the tolerance-widened ones."""

    filters: CandidateFilter
    models: tuple[str, ...] = ()
    cities: tuple[str, ...] = ()
    gearbox: Gearbox | None = None


@dataclass(frozen=True, slots=True)
class FacetRow:
    value: str
    count: int
    brand: str | None = None  # model rows only


@dataclass(frozen=True, slots=True)
class FacetRanges:
    price_min: int | None
    price_max: int | None
    km_min: int | None
    km_max: int | None
    year_min: int | None
    year_max: int | None


def _within(
    column: Any, floor: int | None, ceiling: int | None
) -> list[ColumnElement[bool]]:
    bounds: list[ColumnElement[bool]] = []
    if floor is not None:
        bounds.append(column.is_(None) | (column >= floor))
    if ceiling is not None:
        bounds.append(column.is_(None) | (column <= ceiling))
    return bounds


_FACET_COLUMNS: Mapping[FacetDimension, Any] = {
    FacetDimension.CATEGORY: Listing.category,
    FacetDimension.MODEL: VehicleCatalog.model,
    FacetDimension.CITY: City.name,
    FacetDimension.SOURCE: Listing.source,
    FacetDimension.GEARBOX: Listing.gearbox,
}


class ListingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(self, rows: Sequence[Mapping[str, Any]]) -> None:
        for start in range(0, len(rows), UPSERT_BATCH_SIZE):
            statement = insert(Listing).values(
                list(rows[start : start + UPSERT_BATCH_SIZE])
            )
            updatable = {
                name: statement.excluded[name]
                for name in rows[start]
                if name not in _IMMUTABLE_COLUMNS
            }
            await self._session.execute(
                statement.on_conflict_do_update(
                    index_elements=[Listing.token], set_=updatable
                )
            )

    async def load_estimator_inputs(
        self, category: Category | None = None
    ) -> list[EstimatorInput]:
        statement = select(
            Listing.id,
            Listing.category,
            VehicleCatalog.trim,
            VehicleCatalog.model,
            Listing.year,
            Listing.km,
            Listing.price,
            Listing.insurance_months,
            Listing.body_condition,
            Listing.source,  # positional: keep in step with EstimatorInput's fields
        ).outerjoin(VehicleCatalog, Listing.catalog_id == VehicleCatalog.id)
        if category is not None:
            statement = statement.where(Listing.category == category)
        found = await self._session.execute(statement)
        return [EstimatorInput(*row) for row in found]

    async def apply_estimates(self, estimates: Sequence[Estimate]) -> None:
        rows = [{"id": row.pop("listing_id"), **row} for row in map(asdict, estimates)]
        for start in range(0, len(rows), UPSERT_BATCH_SIZE):
            await self._session.execute(
                update(Listing), rows[start : start + UPSERT_BATCH_SIZE]
            )

    async def load_model_rows(self, model: str) -> list[ModelRow]:
        trusted_price = case((Listing.price_suspect, null()), else_=Listing.price)
        found = await self._session.execute(
            select(
                Listing.id,
                VehicleCatalog.trim,
                Listing.year,
                trusted_price,
                Listing.deal_score,
            )
            .join(VehicleCatalog, Listing.catalog_id == VehicleCatalog.id)
            .where(VehicleCatalog.model == model)
        )
        return [
            ModelRow(
                listing_id=listing_id,
                trim=trim,
                year=year,
                price=price,
                deal_score=deal_score,
            )
            for listing_id, trim, year, price, deal_score in found
        ]

    async def newest_fetched_at(self) -> datetime | None:
        return await self._session.scalar(select(func.max(Listing.fetched_at)))

    async def count(self) -> int:
        return (
            await self._session.scalar(select(func.count()).select_from(Listing)) or 0
        )

    async def count_by_category(
        self, category: Category | None = None
    ) -> dict[Category, int]:
        statement = select(Listing.category, func.count()).group_by(Listing.category)
        if category is not None:
            statement = statement.where(Listing.category == category)
        found = await self._session.execute(statement)
        return dict(found.all())

    async def count_facet(
        self, scope: FacetScope, dimension: FacetDimension, limit: int
    ) -> list[FacetRow]:
        """Listings per option of one filter, within all else the search asked."""
        value = _FACET_COLUMNS[dimension]
        # Postgres rejects a constant in GROUP BY, so only model rows carry a brand.
        with_brand = dimension is FacetDimension.MODEL
        grouped = (value, VehicleCatalog.brand) if with_brand else (value,)
        total = func.count().label("total")
        statement = (
            self._joined(select(*grouped, total))
            .where(value.is_not(None), *self._scope_conditions(scope, dimension))
            .group_by(*grouped)
            .order_by(total.desc(), value)
            .limit(limit)
        )
        found = await self._session.execute(statement)
        return [
            FacetRow(
                value=str(row[0]), count=row[-1], brand=row[1] if with_brand else None
            )
            for row in found
        ]

    async def facet_ranges(self, scope: FacetScope) -> FacetRanges:
        """The spread of price, km and year the search could still reach — its own
        range bounds left out, otherwise the answer would just echo them."""
        unbounded = cast(
            CandidateFilter,
            replace(
                scope.filters,
                price_floor=None,
                price_ceiling=None,
                km_floor=None,
                km_ceiling=None,
                year_floor=None,
                year_ceiling=None,
            ),
        )
        trusted_price = case((Listing.price_suspect, null()), else_=Listing.price)
        unbounded_scope = cast(FacetScope, replace(scope, filters=unbounded))
        statement = self._joined(
            select(
                func.min(trusted_price),
                func.max(trusted_price),
                func.min(Listing.km),
                func.max(Listing.km),
                func.min(Listing.year),
                func.max(Listing.year),
            )
        ).where(*self._scope_conditions(unbounded_scope, None))
        price_min, price_max, km_min, km_max, year_min, year_max = (
            await self._session.execute(statement)
        ).one()
        return FacetRanges(
            price_min=price_min,
            price_max=price_max,
            km_min=km_min,
            km_max=km_max,
            year_min=year_min,
            year_max=year_max,
        )

    @staticmethod
    def _joined(statement: Select[Any]) -> Select[Any]:
        return (
            statement.select_from(Listing)
            .join(City, Listing.city_id == City.id)
            .outerjoin(VehicleCatalog, Listing.catalog_id == VehicleCatalog.id)
        )

    @classmethod
    def _scope_conditions(
        cls, scope: FacetScope, counted: FacetDimension | None
    ) -> list[ColumnElement[bool]]:
        filters = scope.filters
        if counted is FacetDimension.CATEGORY:
            filters = replace(filters, category=None)
        if counted is FacetDimension.SOURCE:
            filters = replace(filters, sources=())
        conditions = cls._conditions(filters)
        if scope.models and counted is not FacetDimension.MODEL:
            conditions.append(VehicleCatalog.model.in_(scope.models))
        if scope.cities and counted is not FacetDimension.CITY:
            conditions.append(City.name.in_(scope.cities))
        if scope.gearbox is not None and counted is not FacetDimension.GEARBOX:
            conditions.append(Listing.gearbox == scope.gearbox)
        return conditions

    async def get_by_id(self, listing_id: uuid.UUID) -> Listing | None:
        found = await self.get_by_ids([listing_id])
        return found[0] if found else None

    async def get_by_ids(self, listing_ids: Sequence[uuid.UUID]) -> list[Listing]:
        found = await self._session.scalars(
            select(Listing)
            .options(joinedload(Listing.city), joinedload(Listing.catalog))
            .where(Listing.id.in_(listing_ids))
        )
        by_id = {listing.id: listing for listing in found}
        return [by_id[listing_id] for listing_id in listing_ids if listing_id in by_id]

    async def find_candidates(
        self, filters: CandidateFilter, limit: int
    ) -> list[Candidate]:
        statement = self._candidate_columns(filters.text)
        for condition in self._conditions(filters):
            statement = statement.where(condition)
        statement = statement.order_by(
            Listing.deal_score.desc().nulls_last(), Listing.id
        )
        found = await self._session.execute(statement.limit(limit))
        return [Candidate(*row) for row in found]

    @staticmethod
    def _candidate_columns(text: str | None) -> Select[Any]:
        similarity = (
            func.word_similarity(literal(text), Listing.title_normalized)
            if text
            else null()
        )
        # A suspect price is hidden from the ranker: a deposit never "fits the budget".
        trusted_price = case((Listing.price_suspect, null()), else_=Listing.price)
        return (
            select(
                Listing.id,
                VehicleCatalog.brand,
                VehicleCatalog.model,
                VehicleCatalog.trim,
                Listing.year,
                Listing.km,
                trusted_price.label("price"),
                City.name.label("city"),
                func.coalesce(Listing.lat, City.lat).label("lat"),
                func.coalesce(Listing.lng, City.lng).label("lng"),
                Listing.gearbox,
                Listing.fuel,
                Listing.color,
                similarity.label("text_similarity"),
                Listing.deal_score,
                Listing.posted_at,
            )
            .join(City, Listing.city_id == City.id)
            .outerjoin(VehicleCatalog, Listing.catalog_id == VehicleCatalog.id)
        )

    @staticmethod
    def _conditions(filters: CandidateFilter) -> list[ColumnElement[bool]]:
        trusted_price = case((Listing.price_suspect, null()), else_=Listing.price)
        conditions = [
            *_within(trusted_price, filters.price_floor, filters.price_ceiling),
            *_within(Listing.km, filters.km_floor, filters.km_ceiling),
            *_within(Listing.year, filters.year_floor, filters.year_ceiling),
        ]
        if filters.category is not None:
            conditions.append(Listing.category == filters.category)
        if filters.sources:
            conditions.append(Listing.source.in_(filters.sources))
        if filters.price_types:
            conditions.append(
                or_(
                    Listing.price_type.in_(filters.price_types),
                    Listing.price_type.is_(None),
                )
            )
        if filters.document_statuses:
            conditions.append(
                or_(
                    Listing.document_status.in_(filters.document_statuses),
                    Listing.document_status.is_(None),
                )
            )
        if filters.brands:
            conditions.append(VehicleCatalog.brand.in_(filters.brands))
        elif filters.text:
            similarity = func.word_similarity(
                literal(filters.text), Listing.title_normalized
            )
            conditions.append(similarity >= MIN_TEXT_SIMILARITY)
        if filters.only_below_market:
            conditions.append(Listing.diff_pct <= CHEAP_DIFF_PCT)
        if filters.exclude_id is not None:
            conditions.append(Listing.id != filters.exclude_id)
        return conditions
