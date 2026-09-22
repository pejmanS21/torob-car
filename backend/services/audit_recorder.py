from typing import Any

from enums import AdminAction
from models.admin_audit import AdminAudit
from repositories.admin_audit_repository import AdminAuditRepository
from schemas.admin import AuditRow
from schemas.auth import UserRead


class AuditRecorder:
    """The single way an audit row is written. Callers pass an already-redacted
    summary — nothing here inspects it, so a secret placed in a summary would be
    stored verbatim. Keeping secrets out is the calling service's job."""

    def __init__(self, repository: AdminAuditRepository) -> None:
        self._repository = repository

    async def record(
        self,
        *,
        actor: UserRead,
        action: AdminAction,
        target_type: str,
        target_id: str | None,
        summary: dict[str, Any],
    ) -> None:
        await self._repository.add(
            AdminAudit(
                actor_id=actor.id,
                actor_email=actor.email,
                action=action,
                target_type=target_type,
                target_id=target_id,
                summary=summary,
            )
        )

    async def recent(self, limit: int) -> list[AuditRow]:
        rows = await self._repository.list_page(limit, 0, None, None)
        return [AuditRow.model_validate(row) for row in rows]
