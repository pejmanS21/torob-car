import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.price_alert import PriceAlert


class PriceAlertRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_user(self, user_id: uuid.UUID) -> list[PriceAlert]:
        found = await self._session.scalars(
            select(PriceAlert)
            .where(PriceAlert.user_id == user_id)
            .order_by(PriceAlert.created_at, PriceAlert.id)
        )
        return list(found)

    async def add(self, alert: PriceAlert) -> PriceAlert:
        self._session.add(alert)
        await self._session.flush()
        return alert

    async def remove(self, user_id: uuid.UUID, alert_id: uuid.UUID) -> bool:
        """Scoped by owner: someone else's alert is indistinguishable from none."""
        result = await self._session.execute(
            delete(PriceAlert)
            .where(PriceAlert.id == alert_id, PriceAlert.user_id == user_id)
            .returning(PriceAlert.id)
        )
        return result.first() is not None
