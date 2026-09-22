import uuid

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from enums import UserRole
from models.price_alert import PriceAlert
from models.saved_listing import SavedListing
from models.user import User


class AdminUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search(
        self,
        term: str | None,
        role: UserRole | None,
        is_active: bool | None,
        limit: int,
        offset: int,
    ) -> list[User]:
        found = await self._session.scalars(
            select(User)
            .where(*self._conditions(term, role, is_active))
            .order_by(User.created_at.desc(), User.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(found)

    async def count(
        self, term: str | None, role: UserRole | None, is_active: bool | None
    ) -> int:
        total = await self._session.scalar(
            select(func.count())
            .select_from(User)
            .where(*self._conditions(term, role, is_active))
        )
        return total or 0

    async def lock_active_admin_ids(self) -> list[uuid.UUID]:
        """SELECT ... FOR UPDATE over the active admins. The row lock is what makes the
        last-admin guard safe: two concurrent demotions serialise here instead of both
        reading "two admins" and both going ahead."""
        found = await self._session.scalars(
            select(User.id)
            .where(User.role == UserRole.ADMIN, User.is_active.is_(True))
            .order_by(User.id)
            .with_for_update()
        )
        return list(found)

    async def remove(self, user: User) -> None:
        await self._session.delete(user)
        await self._session.flush()

    async def saved_and_alert_counts(self, user_id: uuid.UUID) -> tuple[int, int]:
        saved = await self._session.scalar(
            select(func.count())
            .select_from(SavedListing)
            .where(SavedListing.user_id == user_id)
        )
        alerts = await self._session.scalar(
            select(func.count())
            .select_from(PriceAlert)
            .where(PriceAlert.user_id == user_id)
        )
        return saved or 0, alerts or 0

    @staticmethod
    def _conditions(
        term: str | None, role: UserRole | None, is_active: bool | None
    ) -> list[ColumnElement[bool]]:
        conditions: list[ColumnElement[bool]] = []
        if term:
            conditions.append(User.email.ilike(f"%{term}%"))
        if role is not None:
            conditions.append(User.role == role)
        if is_active is not None:
            conditions.append(User.is_active.is_(is_active))
        return conditions
