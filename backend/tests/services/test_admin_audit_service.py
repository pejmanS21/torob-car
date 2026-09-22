import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from enums import AdminAction
from models.admin_audit import AdminAudit
from repositories.admin_audit_repository import AdminAuditRepository
from services.admin_audit_service import AdminAuditService

ACTOR_ID = uuid.UUID(int=1)


def _row() -> AdminAudit:
    return AdminAudit(
        id=uuid.UUID(int=2),
        actor_id=ACTOR_ID,
        actor_email="admin@example.com",
        action=AdminAction.USER_DISABLED,
        target_type="user",
        target_id=str(uuid.UUID(int=3)),
        summary={},
        created_at=datetime.now(UTC),
    )


async def test_list_page_passes_filters_through_and_shapes_the_page() -> None:
    repository = AsyncMock(spec=AdminAuditRepository)
    repository.list_page.return_value = [_row()]
    repository.count.return_value = 1
    service = AdminAuditService(repository)

    page = await service.list_page(AdminAction.USER_DISABLED, ACTOR_ID, 50, 10)

    repository.list_page.assert_awaited_once_with(
        50, 10, AdminAction.USER_DISABLED, ACTOR_ID
    )
    repository.count.assert_awaited_once_with(AdminAction.USER_DISABLED, ACTOR_ID)
    assert page.total == 1
    assert page.items[0].id == uuid.UUID(int=2)
