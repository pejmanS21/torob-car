"""User administration. Every mutation is guarded against lockout and audited in the
same transaction as the change itself."""

import asyncio
import uuid
from typing import Any

from core.config import Settings
from core.security import hash_password
from enums import AdminAction, UserRole
from errors import CannotModifySelfError, LastAdminError, NotAuthenticatedError
from models.user import User
from repositories.admin_user_repository import AdminUserRepository
from repositories.user_repository import UserRepository
from schemas.admin import (
    AdminPasswordReset,
    AdminUserDetail,
    AdminUserPage,
    AdminUserRow,
    AdminUserUpdate,
)
from schemas.auth import UserRead
from services.audit_recorder import AuditRecorder

TARGET_USER = "user"


class AdminUserService:
    def __init__(
        self,
        users: UserRepository,
        admin_users: AdminUserRepository,
        audit: AuditRecorder,
        settings: Settings,
    ) -> None:
        self._users = users
        self._admin_users = admin_users
        self._audit = audit
        self._settings = settings

    async def list_users(
        self,
        term: str | None,
        role: UserRole | None,
        is_active: bool | None,
        limit: int,
        offset: int,
    ) -> AdminUserPage:
        rows = await self._admin_users.search(term, role, is_active, limit, offset)
        return AdminUserPage(
            items=[AdminUserRow.model_validate(row) for row in rows],
            total=await self._admin_users.count(term, role, is_active),
        )

    async def get_user(self, user_id: uuid.UUID) -> AdminUserDetail:
        return await self._detail(await self._load(user_id))

    async def update_user(
        self, actor: UserRead, user_id: uuid.UUID, payload: AdminUserUpdate
    ) -> AdminUserDetail:
        user = await self._load(user_id)
        before = {"is_active": user.is_active, "role": user.role.value}
        if _removes_admin_access(payload):
            await self._guard_lockout(actor, user)
        if payload.is_active is not None:
            user.is_active = payload.is_active
        if payload.role is not None:
            user.role = payload.role
        after = {"is_active": user.is_active, "role": user.role.value}
        await self._audit.record(
            actor=actor,
            action=_action_for(before, after),
            target_type=TARGET_USER,
            target_id=str(user.id),
            summary={"email": user.email, "before": before, "after": after},
        )
        return await self._detail(user)

    async def reset_password(
        self, actor: UserRead, user_id: uuid.UUID, payload: AdminPasswordReset
    ) -> None:
        user = await self._load(user_id)
        password = payload.new.get_secret_value()
        new_hash = await asyncio.to_thread(
            hash_password, password, self._settings.scrypt_n
        )
        # replace_password also bumps token_version, signing the user out everywhere.
        await self._users.replace_password(user, new_hash)
        await self._audit.record(
            actor=actor,
            action=AdminAction.USER_PASSWORD_RESET,
            target_type=TARGET_USER,
            target_id=str(user.id),
            # The new password is deliberately absent — only the fact of the reset.
            summary={"email": user.email},
        )

    async def remove_user(self, actor: UserRead, user_id: uuid.UUID) -> None:
        user = await self._load(user_id)
        await self._guard_lockout(actor, user)
        summary = {"email": user.email, "role": user.role.value}
        await self._admin_users.remove(user)
        await self._audit.record(
            actor=actor,
            action=AdminAction.USER_DELETED,
            target_type=TARGET_USER,
            target_id=str(user_id),
            summary=summary,
        )

    async def _guard_lockout(self, actor: UserRead, user: User) -> None:
        """Only called when an action would remove an admin's access."""
        if user.id == actor.id:
            raise CannotModifySelfError()
        if user.role is not UserRole.ADMIN:
            return  # a plain user can never be the last admin
        remaining = await self._admin_users.lock_active_admin_ids()
        if not [admin_id for admin_id in remaining if admin_id != user.id]:
            raise LastAdminError()

    async def _load(self, user_id: uuid.UUID) -> User:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise NotAuthenticatedError()
        return user

    async def _detail(self, user: User) -> AdminUserDetail:
        saved, alerts = await self._admin_users.saved_and_alert_counts(user.id)
        return AdminUserDetail(
            **AdminUserRow.model_validate(user).model_dump(),
            saved_count=saved,
            alert_count=alerts,
        )


def _removes_admin_access(payload: AdminUserUpdate) -> bool:
    losing_role = payload.role is not None and payload.role is not UserRole.ADMIN
    return payload.is_active is False or losing_role


def _action_for(before: dict[str, Any], after: dict[str, Any]) -> AdminAction:
    if before["role"] != after["role"]:
        return (
            AdminAction.USER_PROMOTED
            if after["role"] == UserRole.ADMIN.value
            else AdminAction.USER_DEMOTED
        )
    return AdminAction.USER_ENABLED if after["is_active"] else AdminAction.USER_DISABLED
