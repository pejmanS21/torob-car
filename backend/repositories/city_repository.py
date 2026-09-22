import uuid
from collections.abc import Collection, Sequence

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.text import normalize_persian
from models.city import City
from models.listing import Listing

MEDIAN = 0.5


class CityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_names(self, names: Collection[str]) -> dict[str, uuid.UUID]:
        if names:
            rows = [
                {"name": name, "name_normalized": normalize_persian(name)}
                for name in sorted(names)
            ]
            statement = insert(City).values(rows)
            await self._session.execute(
                statement.on_conflict_do_nothing(index_elements=[City.name])
            )
        found = await self._session.execute(select(City.name, City.id))
        return dict(found.all())

    async def refresh_statistics(self) -> None:
        """Centroid = median of the city's listing coordinates (no gazetteer)."""
        per_city = (
            select(
                Listing.city_id.label("city_id"),
                func.percentile_cont(MEDIAN).within_group(Listing.lat).label("lat"),
                func.percentile_cont(MEDIAN).within_group(Listing.lng).label("lng"),
                func.count().label("listing_count"),
            )
            .group_by(Listing.city_id)
            .subquery()
        )
        await self._session.execute(
            update(City)
            .where(City.id == per_city.c.city_id)
            .values(
                lat=per_city.c.lat,
                lng=per_city.c.lng,
                listing_count=per_city.c.listing_count,
            )
        )

    async def find_by_names(self, names: Sequence[str]) -> list[City]:
        normalized = [normalize_persian(name) for name in names]
        found = await self._session.scalars(
            select(City).where(City.name_normalized.in_(normalized))
        )
        return list(found)

    async def list_names(self) -> list[str]:
        found = await self._session.scalars(
            select(City.name).order_by(City.listing_count.desc())
        )
        return list(found)
