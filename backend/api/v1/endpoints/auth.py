from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Response, status

from core.config import Settings
from core.security import (
    ACCESS_COOKIE,
    REFRESH_COOKIE,
    REFRESH_COOKIE_PATH,
    TokenPair,
)
from dependencies.providers import CurrentUserDep, SettingsDep, get_auth_service
from schemas.auth import LoginRequest, PasswordChange, UserCreate, UserRead
from services.auth_service import AuthService

SECONDS_PER_DAY = 86_400
ROOT_PATH = "/"
_COOKIE_PATHS = {ACCESS_COOKIE: ROOT_PATH, REFRESH_COOKIE: REFRESH_COOKIE_PATH}

router = APIRouter(prefix="/auth", tags=["auth"])
ServiceDep = Annotated[AuthService, Depends(get_auth_service)]


def _set_auth_cookies(
    response: Response, tokens: TokenPair, settings: Settings
) -> None:
    # Both cookies live as long as the refresh token. The access *token* inside still
    # expires after 15 minutes; keeping its cookie means the backend can answer
    # `token_expired` (→ the client refreshes) instead of `not_authenticated`.
    max_age = settings.refresh_token_days * SECONDS_PER_DAY
    values = {ACCESS_COOKIE: tokens.access, REFRESH_COOKIE: tokens.refresh}
    for name, path in _COOKIE_PATHS.items():
        response.set_cookie(
            name,
            values[name],
            max_age=max_age,
            path=path,
            httponly=True,
            samesite="lax",
            secure=not settings.is_development,
        )


def _clear_auth_cookies(response: Response, settings: Settings) -> None:
    for name, path in _COOKIE_PATHS.items():
        response.delete_cookie(
            name,
            path=path,
            httponly=True,
            samesite="lax",
            secure=not settings.is_development,
        )


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserCreate, response: Response, service: ServiceDep, settings: SettingsDep
) -> UserRead:
    result = await service.register(payload)
    _set_auth_cookies(response, result.tokens, settings)
    return result.user


@router.post("/login")
async def login(
    payload: LoginRequest,
    response: Response,
    service: ServiceDep,
    settings: SettingsDep,
) -> UserRead:
    result = await service.authenticate(payload)
    _set_auth_cookies(response, result.tokens, settings)
    return result.user


@router.post("/refresh")
async def refresh(
    response: Response,
    service: ServiceDep,
    settings: SettingsDep,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> UserRead:
    result = await service.refresh(refresh_token)
    _set_auth_cookies(response, result.tokens, settings)
    return result.user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response, settings: SettingsDep) -> None:
    _clear_auth_cookies(response, settings)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(
    response: Response,
    current: CurrentUserDep,
    service: ServiceDep,
    settings: SettingsDep,
) -> None:
    await service.logout_all(current.user_id)
    _clear_auth_cookies(response, settings)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: PasswordChange,
    response: Response,
    current: CurrentUserDep,
    service: ServiceDep,
    settings: SettingsDep,
) -> None:
    result = await service.change_password(current.user_id, payload)
    _set_auth_cookies(response, result.tokens, settings)
