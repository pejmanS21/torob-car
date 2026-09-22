import asyncio
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from models.anonymous_chat_quota import AnonymousChatQuota
from models.user import utc_now
from repositories.anonymous_chat_quota_repository import AnonymousChatQuotaRepository

pytestmark = pytest.mark.db


async def test_three_replies_then_limit_and_expired_window_resets(
    session: AsyncSession,
) -> None:
    repository = AnonymousChatQuotaRepository(session)
    now = utc_now()
    reset = now + timedelta(days=1)
    for _ in range(3):
        assert (await repository.reserve("visitor", 3, now, reset)).allowed
    denied = await repository.reserve("visitor", 3, now, reset)
    assert not denied.allowed
    assert denied.resets_at == reset
    assert (await repository.reserve("another", 3, now, reset)).allowed
    assert (
        await repository.reserve("visitor", 3, reset, reset + timedelta(days=1))
    ).allowed
    count = await session.scalar(
        select(AnonymousChatQuota.count).where(AnonymousChatQuota.identity == "visitor")
    )
    assert count == 1


async def test_failed_answer_rolls_back_its_reservation(session: AsyncSession) -> None:
    repository = AnonymousChatQuotaRepository(session)
    now = utc_now()
    savepoint = await session.begin_nested()
    assert (
        await repository.reserve("visitor", 3, now, now + timedelta(days=1))
    ).allowed
    await savepoint.rollback()
    for _ in range(3):
        assert (
            await repository.reserve("visitor", 3, now, now + timedelta(days=1))
        ).allowed


async def test_concurrent_workers_cannot_exceed_three(
    migrated_database_url: str,
) -> None:
    engine = create_async_engine(migrated_database_url)
    sessions = async_sessionmaker(engine)
    identity = str(uuid.uuid4())
    now = utc_now()

    async def reserve() -> bool:
        async with sessions.begin() as session:
            result = await AnonymousChatQuotaRepository(session).reserve(
                identity, 3, now, now + timedelta(days=1)
            )
            return result.allowed

    try:
        assert sum(await asyncio.gather(*(reserve() for _ in range(8)))) == 3
    finally:
        async with sessions.begin() as session:
            await session.execute(
                delete(AnonymousChatQuota).where(
                    AnonymousChatQuota.identity == identity
                )
            )
        await engine.dispose()
