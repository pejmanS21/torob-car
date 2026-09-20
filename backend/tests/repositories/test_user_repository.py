import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from enums import UserRole
from repositories.user_repository import UserRepository

pytestmark = pytest.mark.db

EMAIL = "reader@example.com"


async def test_create_if_absent_fills_the_defaults(session: AsyncSession) -> None:
    user = await UserRepository(session).create_if_absent(EMAIL, "hash", UserRole.USER)
    assert user is not None
    assert user.id.version == 8
    assert (user.role, user.is_active, user.token_version) == (UserRole.USER, True, 0)
    assert user.created_at is not None and user.last_login_at is None


async def test_create_if_absent_returns_none_for_a_taken_email(
    session: AsyncSession,
) -> None:
    users = UserRepository(session)
    first = await users.create_if_absent(EMAIL, "first-hash", UserRole.USER)
    second = await users.create_if_absent(EMAIL, "second-hash", UserRole.ADMIN)
    assert first is not None and second is None
    kept = await users.get_by_email(EMAIL)
    assert kept is not None
    assert (kept.password_hash, kept.role) == ("first-hash", UserRole.USER)


async def test_lookups_find_the_user_or_return_none(session: AsyncSession) -> None:
    users = UserRepository(session)
    created = await users.create_if_absent(EMAIL, "hash", UserRole.USER)
    assert created is not None
    assert (await users.get_by_id(created.id)) is created
    assert (await users.get_by_email(EMAIL)) is created
    assert await users.get_by_email("nobody@example.com") is None


async def test_replace_password_revokes_existing_tokens(session: AsyncSession) -> None:
    users = UserRepository(session)
    user = await users.create_if_absent(EMAIL, "old-hash", UserRole.USER)
    assert user is not None
    await users.replace_password(user, "new-hash")
    assert (user.password_hash, user.token_version) == ("new-hash", 1)


async def test_record_login_and_bump_token_version(session: AsyncSession) -> None:
    users = UserRepository(session)
    user = await users.create_if_absent(EMAIL, "hash", UserRole.USER)
    assert user is not None
    await users.record_login(user)
    await users.bump_token_version(user)
    assert user.last_login_at is not None and user.token_version == 1
