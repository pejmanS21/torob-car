import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from dependencies.providers import FreshAdminDep, get_admin_user_service
from enums import UserRole
from schemas.admin import (
    MAX_PAGE_SIZE,
    AdminPasswordReset,
    AdminUserDetail,
    AdminUserPage,
    AdminUserUpdate,
)
from services.admin_user_service import AdminUserService

router = APIRouter(prefix="/users")
ServiceDep = Annotated[AdminUserService, Depends(get_admin_user_service)]


@router.get("")
async def list_users(
    service: ServiceDep,
    term: str | None = None,
    role: UserRole | None = None,
    is_active: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminUserPage:
    return await service.list_users(term, role, is_active, limit, offset)


@router.get("/{user_id}")
async def read_user(user_id: uuid.UUID, service: ServiceDep) -> AdminUserDetail:
    return await service.get_user(user_id)


@router.patch("/{user_id}")
async def update_user(
    user_id: uuid.UUID,
    payload: AdminUserUpdate,
    actor: FreshAdminDep,
    service: ServiceDep,
) -> AdminUserDetail:
    return await service.update_user(actor, user_id, payload)


@router.post("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    user_id: uuid.UUID,
    payload: AdminPasswordReset,
    actor: FreshAdminDep,
    service: ServiceDep,
) -> None:
    await service.reset_password(actor, user_id, payload)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_user(
    user_id: uuid.UUID, actor: FreshAdminDep, service: ServiceDep
) -> None:
    await service.remove_user(actor, user_id)
