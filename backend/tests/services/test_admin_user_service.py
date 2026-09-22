import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from core.security import verify_password
from enums import AdminAction, UserRole
from errors import AdminUserNotFoundError, CannotModifySelfError, LastAdminError
from models.user import User
from repositories.admin_user_repository import AdminUserRepository
from repositories.user_repository import UserRepository
from schemas.admin import AdminPasswordReset, AdminUserUpdate
from schemas.auth import UserRead
from services.admin_user_service import AdminUserService
from services.audit_recorder import AuditRecorder
from tests.support import fast_auth_settings

ACTOR_ID = uuid.UUID(int=1)
TARGET_ID = uuid.UUID(int=2)


def _row(
    user_id: uuid.UUID, role: UserRole = UserRole.USER, active: bool = True
) -> User:
    return User(
        id=user_id,
        email=f"user-{user_id.int}@example.com",
        password_hash="hash",
        role=role,
        is_active=active,
        token_version=0,
        created_at=datetime.now(UTC),
        last_login_at=None,
    )


def _actor() -> UserRead:
    return UserRead.model_validate(_row(ACTOR_ID, UserRole.ADMIN))


class Doubles:
    def __init__(self, target: User | None, active_admin_ids: list[uuid.UUID]) -> None:
        self.users = AsyncMock(spec=UserRepository)
        self.admin_users = AsyncMock(spec=AdminUserRepository)
        self.audit = AsyncMock(spec=AuditRecorder)
        self.users.get_by_id.return_value = target
        self.admin_users.lock_active_admin_ids.return_value = active_admin_ids
        self.admin_users.saved_and_alert_counts.return_value = (0, 0)
        self.service = AdminUserService(
            self.users, self.admin_users, self.audit, fast_auth_settings()
        )


async def test_an_admin_cannot_disable_themselves() -> None:
    doubles = Doubles(_row(ACTOR_ID, UserRole.ADMIN), [ACTOR_ID, TARGET_ID])
    with pytest.raises(CannotModifySelfError):
        await doubles.service.update_user(
            _actor(), ACTOR_ID, AdminUserUpdate(is_active=False)
        )
    doubles.audit.record.assert_not_awaited()


async def test_an_admin_cannot_remove_themselves() -> None:
    doubles = Doubles(_row(ACTOR_ID, UserRole.ADMIN), [ACTOR_ID, TARGET_ID])
    with pytest.raises(CannotModifySelfError):
        await doubles.service.remove_user(_actor(), ACTOR_ID)
    doubles.admin_users.remove.assert_not_awaited()


@pytest.mark.parametrize(
    "update", [AdminUserUpdate(is_active=False), AdminUserUpdate(role=UserRole.USER)]
)
async def test_the_last_active_admin_cannot_be_demoted_or_disabled(
    update: AdminUserUpdate,
) -> None:
    doubles = Doubles(_row(TARGET_ID, UserRole.ADMIN), [TARGET_ID])
    with pytest.raises(LastAdminError):
        await doubles.service.update_user(_actor(), TARGET_ID, update)
    doubles.audit.record.assert_not_awaited()


async def test_demoting_an_admin_is_allowed_while_another_remains() -> None:
    doubles = Doubles(_row(TARGET_ID, UserRole.ADMIN), [ACTOR_ID, TARGET_ID])
    await doubles.service.update_user(
        _actor(), TARGET_ID, AdminUserUpdate(role=UserRole.USER)
    )
    assert doubles.audit.record.call_args.kwargs["action"] is AdminAction.USER_DEMOTED


async def test_disabling_a_plain_user_never_consults_the_admin_lock() -> None:
    doubles = Doubles(_row(TARGET_ID), [ACTOR_ID])
    await doubles.service.update_user(
        _actor(), TARGET_ID, AdminUserUpdate(is_active=False)
    )
    doubles.admin_users.lock_active_admin_ids.assert_not_awaited()
    assert doubles.audit.record.call_args.kwargs["action"] is AdminAction.USER_DISABLED


async def test_resetting_a_password_hashes_it_and_revokes_existing_tokens() -> None:
    doubles = Doubles(_row(TARGET_ID), [ACTOR_ID])
    await doubles.service.reset_password(
        _actor(), TARGET_ID, AdminPasswordReset(new="a brand new password")
    )
    _, stored_hash = doubles.users.replace_password.call_args.args
    assert verify_password("a brand new password", stored_hash)
    assert (
        doubles.audit.record.call_args.kwargs["action"]
        is AdminAction.USER_PASSWORD_RESET
    )


async def test_the_reset_password_never_reaches_the_audit_summary() -> None:
    doubles = Doubles(_row(TARGET_ID), [ACTOR_ID])
    await doubles.service.reset_password(
        _actor(), TARGET_ID, AdminPasswordReset(new="a brand new password")
    )
    assert "a brand new password" not in str(
        doubles.audit.record.call_args.kwargs["summary"]
    )


async def test_acting_on_a_missing_user_raises() -> None:
    doubles = Doubles(None, [ACTOR_ID])
    with pytest.raises(AdminUserNotFoundError):
        await doubles.service.get_user(TARGET_ID)
