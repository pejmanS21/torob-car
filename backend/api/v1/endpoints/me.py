import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from dependencies.providers import (
    CurrentUserDep,
    get_account_service,
    get_auth_service,
)
from schemas.account import (
    AccountState,
    ImportRequest,
    PriceAlertCreate,
    PriceAlertRead,
)
from schemas.auth import UserRead
from services.account_service import AccountService
from services.auth_service import AuthService

router = APIRouter(prefix="/me", tags=["me"])
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
AccountServiceDep = Annotated[AccountService, Depends(get_account_service)]


@router.get("")
async def read_me(current: CurrentUserDep, service: AuthServiceDep) -> UserRead:
    return await service.get_user(current.user_id)


@router.get("/saved")
async def read_saved(
    current: CurrentUserDep, service: AccountServiceDep
) -> list[uuid.UUID]:
    return await service.list_saved(current.user_id)


@router.put("/saved/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def save_listing(
    listing_id: uuid.UUID, current: CurrentUserDep, service: AccountServiceDep
) -> None:
    await service.save_listing(current.user_id, listing_id)


@router.delete("/saved/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unsave_listing(
    listing_id: uuid.UUID, current: CurrentUserDep, service: AccountServiceDep
) -> None:
    await service.unsave_listing(current.user_id, listing_id)


@router.get("/alerts")
async def read_alerts(
    current: CurrentUserDep, service: AccountServiceDep
) -> list[PriceAlertRead]:
    return await service.list_alerts(current.user_id)


@router.post("/alerts", status_code=status.HTTP_201_CREATED)
async def create_alert(
    payload: PriceAlertCreate, current: CurrentUserDep, service: AccountServiceDep
) -> PriceAlertRead:
    return await service.create_alert(current.user_id, payload)


@router.delete("/alerts/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert(
    alert_id: uuid.UUID, current: CurrentUserDep, service: AccountServiceDep
) -> None:
    await service.delete_alert(current.user_id, alert_id)


@router.post("/import")
async def import_state(
    payload: ImportRequest, current: CurrentUserDep, service: AccountServiceDep
) -> AccountState:
    return await service.import_state(current.user_id, payload)
