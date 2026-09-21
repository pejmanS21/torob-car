import uuid

from enums import AdminAction
from repositories.admin_audit_repository import AdminAuditRepository
from schemas.admin import AuditPage, AuditRow


class AdminAuditService:
    def __init__(self, repository: AdminAuditRepository) -> None:
        self._repository = repository

    async def list_page(
        self,
        action: AdminAction | None,
        actor_id: uuid.UUID | None,
        limit: int,
        offset: int,
    ) -> AuditPage:
        rows = await self._repository.list_page(limit, offset, action, actor_id)
        return AuditPage(
            items=[AuditRow.model_validate(row) for row in rows],
            total=await self._repository.count(action, actor_id),
        )
