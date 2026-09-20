from typing import Annotated

from fastapi import APIRouter, Depends

from dependencies.providers import CurrentUserDep, get_auth_service
from schemas.auth import UserRead
from services.auth_service import AuthService

router = APIRouter(prefix="/me", tags=["me"])
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


@router.get("", response_model=UserRead)
async def read_me(current: CurrentUserDep, service: AuthServiceDep) -> UserRead:
    return await service.get_user(current.user_id)
