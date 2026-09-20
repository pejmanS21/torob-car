import uuid
from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.saved_listing import SavedListing


class SavedListingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_listing_ids(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        found = await self._session.scalars(
            select(SavedListing.listing_id)
            .where(SavedListing.user_id == user_id)
            .order_by(SavedListing.created_at.desc(), SavedListing.id.desc())
        )
        return list(found)

    async def add_many(
        self, user_id: uuid.UUID, listing_ids: Sequence[uuid.UUID]
    ) -> None:
        if not listing_ids:
            return
        rows = [{"user_id": user_id, "listing_id": item} for item in listing_ids]
        statement = insert(SavedListing).values(rows)
        await self._session.execute(
            statement.on_conflict_do_nothing(
                index_elements=[SavedListing.user_id, SavedListing.listing_id]
            )
        )

    async def remove(self, user_id: uuid.UUID, listing_id: uuid.UUID) -> None:
        await self._session.execute(
            delete(SavedListing).where(
                SavedListing.user_id == user_id, SavedListing.listing_id == listing_id
            )
        )
