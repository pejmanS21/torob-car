"""SSE transport owns transaction completion before announcing a saved answer."""

import json
import logging
from collections.abc import AsyncIterator
from contextlib import aclosing

import anyio
from sqlalchemy.ext.asyncio import AsyncSession

from errors import AppError, AssistantUnavailableError
from schemas.assistant import AssistantResponse, AssistantTextUpdate

logger = logging.getLogger(__name__)


def _event(name: str, data: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def assistant_events(
    updates: AsyncIterator[AssistantTextUpdate | AssistantResponse],
    session: AsyncSession,
    *,
    charge_on_text: bool = False,
) -> AsyncIterator[str]:
    completed = False
    try:
        yield ": connected\n\n"
        async with aclosing(updates):
            async for update in updates:
                if isinstance(update, AssistantResponse):
                    await session.commit()
                    completed = True
                    yield _event("done", update.model_dump(mode="json"))
                else:
                    if charge_on_text:
                        # Once useful text is delivered, cancelling cannot refund a
                        # guest's slot. Failures before any text still roll back.
                        await session.commit()
                        charge_on_text = False
                    yield _event("text", update.model_dump(mode="json"))
        if not completed:
            raise AssistantUnavailableError()
    except Exception as error:
        logger.warning("assistant stream interrupted", exc_info=error)
        public = error if isinstance(error, AppError) else AssistantUnavailableError()
        yield _event("error", {"code": public.code, "message": public.message})
    finally:
        if not completed:
            # Client disconnects cancel the response task; still release quota/locks.
            with anyio.CancelScope(shield=True):
                await session.rollback()
