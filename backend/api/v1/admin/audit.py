import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from dependencies.providers import get_admin_audit_service
from enums import AdminAction
from schemas.admin import MAX_PAGE_SIZE, AuditPage
from services.admin_audit_service import AdminAuditService

router = APIRouter(prefix="/audit")
ServiceDep = Annotated[AdminAuditService, Depends(get_admin_audit_service)]


@router.get("")
async def list_audit(
    service: ServiceDep,
    action: AdminAction | None = None,
    actor_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AuditPage:
    return await service.list_page(action, actor_id, limit, offset)
