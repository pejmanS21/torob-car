import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from dependencies.providers import SessionDep
from enums import AdminAction
from repositories.admin_audit_repository import AdminAuditRepository
from schemas.admin import MAX_PAGE_SIZE, AuditPage, AuditRow

router = APIRouter(prefix="/audit")


@router.get("")
async def list_audit(
    session: SessionDep,
    action: AdminAction | None = None,
    actor_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AuditPage:
    repository = AdminAuditRepository(session)
    rows = await repository.list_page(limit, offset, action, actor_id)
    return AuditPage(
        items=[AuditRow.model_validate(row) for row in rows],
        total=await repository.count(action, actor_id),
    )
