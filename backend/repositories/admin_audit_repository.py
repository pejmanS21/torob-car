import uuid

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from enums import AdminAction
from models.admin_audit import AdminAudit


class AdminAuditRepository:
    """Append and read only. There is deliberately no mutating method — an audit trail
    that can be rewritten is worth nothing."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, entry: AdminAudit) -> AdminAudit:
        self._session.add(entry)
        await self._session.flush()
        return entry

    async def list_page(
        self,
        limit: int,
        offset: int,
        action: AdminAction | None,
        actor_id: uuid.UUID | None,
    ) -> list[AdminAudit]:
        found = await self._session.scalars(
            select(AdminAudit)
            .where(*self._conditions(action, actor_id))
            .order_by(AdminAudit.created_at.desc(), AdminAudit.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(found)

    async def count(
        self, action: AdminAction | None, actor_id: uuid.UUID | None
    ) -> int:
        total = await self._session.scalar(
            select(func.count())
            .select_from(AdminAudit)
            .where(*self._conditions(action, actor_id))
        )
        return total or 0

    @staticmethod
    def _conditions(
        action: AdminAction | None, actor_id: uuid.UUID | None
    ) -> list[ColumnElement[bool]]:
        conditions: list[ColumnElement[bool]] = []
        if action is not None:
            conditions.append(AdminAudit.action == action)
        if actor_id is not None:
            conditions.append(AdminAudit.actor_id == actor_id)
        return conditions
