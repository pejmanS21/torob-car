import uuid

import pytest
from sqlalchemy import delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession

from enums import AdminAction, UserRole
from models.admin_audit import AdminAudit
from models.user import User
from repositories.admin_audit_repository import AdminAuditRepository
from repositories.admin_user_repository import AdminUserRepository
from repositories.user_repository import UserRepository

pytestmark = pytest.mark.db


async def _user(
    session: AsyncSession, email: str, role: UserRole = UserRole.USER
) -> User:
    created = await UserRepository(session).create_if_absent(email, "hash", role)
    assert created is not None
    return created


def _entry(actor: User, action: AdminAction) -> AdminAudit:
    return AdminAudit(
        actor_id=actor.id,
        actor_email=actor.email,
        action=action,
        target_type="user",
        target_id=str(uuid.UUID(int=7)),
        summary={"before": {"is_active": True}, "after": {"is_active": False}},
    )


async def test_audit_rows_come_back_newest_first_and_filter_by_action(
    session: AsyncSession,
) -> None:
    audit = AdminAuditRepository(session)
    admin = await _user(session, "admin@example.com", UserRole.ADMIN)
    await audit.add(_entry(admin, AdminAction.USER_DISABLED))
    await audit.add(_entry(admin, AdminAction.USER_PROMOTED))
    newest_first = await audit.list_page(50, 0, None, None)
    assert [row.action for row in newest_first] == [
        AdminAction.USER_PROMOTED,
        AdminAction.USER_DISABLED,
    ]
    assert len(await audit.list_page(50, 0, AdminAction.USER_PROMOTED, None)) == 1
    assert await audit.count(AdminAction.USER_PROMOTED, None) == 1


async def test_removing_the_actor_keeps_the_audit_row_readable(
    session: AsyncSession,
) -> None:
    audit = AdminAuditRepository(session)
    admin = await _user(session, "admin@example.com", UserRole.ADMIN)
    await audit.add(_entry(admin, AdminAction.USER_DELETED))
    await session.execute(sql_delete(User).where(User.id == admin.id))
    await session.flush()
    rows = await audit.list_page(50, 0, None, None)
    assert len(rows) == 1
    assert rows[0].actor_id is None  # SET NULL, not cascaded away
    assert rows[0].actor_email == "admin@example.com"  # still says who did it


async def test_user_search_matches_a_partial_email_and_filters(
    session: AsyncSession,
) -> None:
    users = AdminUserRepository(session)
    await _user(session, "driver@example.com")
    await _user(session, "admin@example.com", UserRole.ADMIN)
    assert len(await users.search("driv", None, None, 50, 0)) == 1
    assert len(await users.search(None, UserRole.ADMIN, None, 50, 0)) == 1
    assert await users.count(None, None, None) == 2


async def test_lock_active_admin_ids_sees_only_active_admins(
    session: AsyncSession,
) -> None:
    users = AdminUserRepository(session)
    admin = await _user(session, "admin@example.com", UserRole.ADMIN)
    retired = await _user(session, "old@example.com", UserRole.ADMIN)
    retired.is_active = False
    await _user(session, "driver@example.com")
    await session.flush()
    assert await users.lock_active_admin_ids() == [admin.id]


async def test_counts_and_removal(session: AsyncSession) -> None:
    users = AdminUserRepository(session)
    user = await _user(session, "driver@example.com")
    assert await users.saved_and_alert_counts(user.id) == (0, 0)
    await users.remove(user)
    assert await users.search("driver", None, None, 50, 0) == []
