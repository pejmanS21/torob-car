import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from enums import UserRole
from models.price_alert import PriceAlert
from models.user import User
from repositories.price_alert_repository import PriceAlertRepository
from repositories.user_repository import UserRepository

pytestmark = pytest.mark.db

PARAMS = {"q": "پژو ۲۰۶", "cities": ["تهران"]}


async def _user(session: AsyncSession, email: str) -> User:
    user = await UserRepository(session).create_if_absent(email, "hash", UserRole.USER)
    assert user is not None
    return user


def _alert(user: User, title: str = "۲۰۶ زیر ۵۰۰") -> PriceAlert:
    return PriceAlert(
        user_id=user.id, title=title, threshold=500_000_000, params=PARAMS
    )


async def test_an_added_alert_is_stored_and_listed(session: AsyncSession) -> None:
    alerts = PriceAlertRepository(session)
    user = await _user(session, "alerts@example.com")
    stored = await alerts.add(_alert(user))
    assert stored.id.version == 8 and stored.created_at is not None
    listed = await alerts.list_for_user(user.id)
    assert [(a.title, a.threshold, a.params) for a in listed] == [
        ("۲۰۶ زیر ۵۰۰", 500_000_000, PARAMS)
    ]


async def test_remove_reports_whether_anything_was_deleted(
    session: AsyncSession,
) -> None:
    alerts = PriceAlertRepository(session)
    user = await _user(session, "alerts@example.com")
    alert = await alerts.add(_alert(user))
    assert await alerts.remove(user.id, alert.id) is True
    assert await alerts.remove(user.id, alert.id) is False


async def test_another_users_alert_cannot_be_removed(session: AsyncSession) -> None:
    alerts = PriceAlertRepository(session)
    owner = await _user(session, "owner@example.com")
    intruder = await _user(session, "intruder@example.com")
    alert = await alerts.add(_alert(owner))
    assert await alerts.remove(intruder.id, alert.id) is False
    assert len(await alerts.list_for_user(owner.id)) == 1


async def test_deleting_the_user_cascades(session: AsyncSession) -> None:
    alerts = PriceAlertRepository(session)
    user = await _user(session, "alerts@example.com")
    await alerts.add(_alert(user))
    await session.execute(delete(User).where(User.id == user.id))
    assert await alerts.list_for_user(user.id) == []
