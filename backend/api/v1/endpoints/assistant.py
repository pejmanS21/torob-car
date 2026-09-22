from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from api.assistant_stream import assistant_events
from dependencies.providers import OptionalUserDep, SessionDep, get_chat_service
from schemas.assistant import AssistantRequest, AssistantResponse
from services.chat_service import ChatService

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("")
async def ask_assistant(
    service: Annotated[ChatService, Depends(get_chat_service)],
    request: AssistantRequest,
    current: OptionalUserDep,
    http_request: Request,
) -> AssistantResponse:
    """Open to anonymous visitors; a logged-in caller also gets the turn stored."""
    return await service.ask(
        request,
        current.user_id if current else None,
        http_request.client.host if http_request.client else "unknown",
    )


@router.post("/stream")
async def stream_assistant(
    service: Annotated[ChatService, Depends(get_chat_service)],
    request: AssistantRequest,
    current: OptionalUserDep,
    http_request: Request,
    session: SessionDep,
) -> StreamingResponse:
    updates = await service.start_stream(
        request,
        current.user_id if current else None,
        http_request.client.host if http_request.client else "unknown",
    )
    return StreamingResponse(
        assistant_events(updates, session, charge_on_text=current is None),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
