from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

DATABASE_PING = text("SELECT 1")


class HealthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ping(self) -> None:
        """Raises OperationalError when the database is unreachable (→ 503)."""
        await self._session.execute(DATABASE_PING)
