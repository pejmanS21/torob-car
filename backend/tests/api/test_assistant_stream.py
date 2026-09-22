from unittest.mock import AsyncMock

import pytest

from api.assistant_stream import assistant_events
from enums import ParsedBy
from errors import AssistantUnavailableError
from schemas.assistant import AssistantResponse, AssistantTextUpdate


async def test_done_is_emitted_only_after_commit() -> None:
    session = AsyncMock()

    async def updates():
        yield AssistantTextUpdate(text="می‌تونی")
        yield AssistantResponse(text="می‌تونی", listings=[], answered_by=ParsedBy.LLM)

    events = []
    async for event in assistant_events(updates(), session):
        if event.startswith("event: done"):
            session.commit.assert_awaited_once()
        events.append(event)
    assert "event: text" in events[1]
    assert "می‌تونی" in events[1]
    session.rollback.assert_not_called()


@pytest.mark.parametrize("commit_fails", [False, True])
async def test_failure_rolls_back_and_emits_error_without_done(
    commit_fails: bool,
) -> None:
    session = AsyncMock()
    if commit_fails:
        session.commit.side_effect = RuntimeError("database unavailable")

    async def updates():
        yield AssistantTextUpdate(text="ناقص")
        if not commit_fails:
            raise AssistantUnavailableError()
        yield AssistantResponse(text="کامل", listings=[], answered_by=ParsedBy.LLM)

    events = [event async for event in assistant_events(updates(), session)]
    assert any("event: error" in event for event in events)
    assert not any("event: done" in event for event in events)
    session.rollback.assert_awaited_once()


async def test_disconnect_closes_generator_and_releases_transaction() -> None:
    session = AsyncMock()
    closed = False

    async def updates():
        nonlocal closed
        try:
            yield AssistantTextUpdate(text="ناقص")
            yield AssistantTextUpdate(text="ادامه")
        finally:
            closed = True

    stream = assistant_events(updates(), session)
    await anext(stream)  # connection comment
    await anext(stream)  # first readable text
    await stream.aclose()
    assert closed
    session.rollback.assert_awaited_once()
    session.commit.assert_not_called()


async def test_guest_disconnect_after_text_does_not_refund_admission() -> None:
    session = AsyncMock()

    async def updates():
        yield AssistantTextUpdate(text="اولین بخش")
        yield AssistantTextUpdate(text="ادامه")

    stream = assistant_events(updates(), session, charge_on_text=True)
    await anext(stream)
    session.commit.assert_not_called()
    assert "event: text" in await anext(stream)
    session.commit.assert_awaited_once()
    await stream.aclose()
    # Rollback only affects work after the committed quota charge.
    session.rollback.assert_awaited_once()
    session.commit.assert_awaited_once()


async def test_guest_failure_before_text_does_not_charge() -> None:
    session = AsyncMock()

    async def updates():
        raise AssistantUnavailableError()
        yield  # make this an async generator

    events = [
        event
        async for event in assistant_events(updates(), session, charge_on_text=True)
    ]
    assert "event: error" in events[-1]
    session.commit.assert_not_called()
    session.rollback.assert_awaited_once()
