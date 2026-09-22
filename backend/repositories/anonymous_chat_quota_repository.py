from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import case, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.anonymous_chat_quota import AnonymousChatQuota


@dataclass(frozen=True, slots=True)
class QuotaReservation:
    allowed: bool
    resets_at: datetime


class AnonymousChatQuotaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def reserve(
        self, identity: str, limit: int, now: datetime, resets_at: datetime
    ) -> QuotaReservation:
        """Atomic admission across workers; rollback releases a failed answer's slot.

        The unique identity row is locked until the request transaction completes,
        so simultaneous requests cannot exceed the limit.
        """
        quota = AnonymousChatQuota
        expired = quota.resets_at <= now
        statement = insert(quota).values(
            identity=identity, count=1, resets_at=resets_at
        )
        admitted = await self._session.scalar(
            statement.on_conflict_do_update(
                index_elements=[quota.identity],
                set_={
                    "count": case((expired, 1), else_=quota.count + 1),
                    "resets_at": case((expired, resets_at), else_=quota.resets_at),
                },
                where=or_(expired, quota.count < limit),
            ).returning(quota.resets_at)
        )
        if admitted is not None:
            return QuotaReservation(True, admitted)
        existing = await self._session.scalar(
            select(quota.resets_at).where(quota.identity == identity)
        )
        assert existing is not None  # the conflicting row is locked by our upsert
        return QuotaReservation(False, existing)
