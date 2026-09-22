import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from enums import UserRole
from models.listing import Listing
from models.user import User
from repositories.saved_listing_repository import SavedListingRepository
from repositories.user_repository import UserRepository

pytestmark = pytest.mark.db


async def _user(session: AsyncSession, email: str = "saver@example.com") -> User:
    user = await UserRepository(session).create_if_absent(email, "hash", UserRole.USER)
    assert user is not None
    return user


async def _listing_ids(session: AsyncSession, count: int) -> list[uuid.UUID]:
    found = await session.scalars(select(Listing.id).order_by(Listing.id).limit(count))
    return list(found)


async def test_saving_twice_is_a_no_op(seeded_session: AsyncSession) -> None:
    saved = SavedListingRepository(seeded_session)
    user = await _user(seeded_session)
    (listing_id,) = await _listing_ids(seeded_session, 1)
    await saved.add_many(user.id, [listing_id])
    await saved.add_many(user.id, [listing_id])
    assert await saved.list_listing_ids(user.id) == [listing_id]


async def test_the_list_is_per_user(seeded_session: AsyncSession) -> None:
    saved = SavedListingRepository(seeded_session)
    first_user = await _user(seeded_session)
    other_user = await _user(seeded_session, "other@example.com")
    one, two = await _listing_ids(seeded_session, 2)
    await saved.add_many(first_user.id, [one, two])
    await saved.add_many(other_user.id, [one])
    assert set(await saved.list_listing_ids(first_user.id)) == {one, two}
    assert await saved.list_listing_ids(other_user.id) == [one]


async def test_remove_is_idempotent(seeded_session: AsyncSession) -> None:
    saved = SavedListingRepository(seeded_session)
    user = await _user(seeded_session)
    (listing_id,) = await _listing_ids(seeded_session, 1)
    await saved.add_many(user.id, [listing_id])
    await saved.remove(user.id, listing_id)
    await saved.remove(user.id, listing_id)
    assert await saved.list_listing_ids(user.id) == []


async def test_add_many_with_nothing_does_nothing(seeded_session: AsyncSession) -> None:
    saved = SavedListingRepository(seeded_session)
    user = await _user(seeded_session)
    await saved.add_many(user.id, [])
    assert await saved.list_listing_ids(user.id) == []


async def test_deleting_the_user_cascades(seeded_session: AsyncSession) -> None:
    saved = SavedListingRepository(seeded_session)
    user = await _user(seeded_session)
    await saved.add_many(user.id, await _listing_ids(seeded_session, 2))
    await seeded_session.execute(delete(User).where(User.id == user.id))
    assert await saved.list_listing_ids(user.id) == []
