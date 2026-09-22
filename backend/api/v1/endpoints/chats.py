import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from dependencies.providers import CurrentUserDep, get_chat_service
from schemas.chat import ChatDetail, ChatSummary
from services.chat_service import ChatService

router = APIRouter(prefix="/me/chats", tags=["chats"])
ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]


@router.get("")
async def read_chats(
    current: CurrentUserDep, service: ChatServiceDep
) -> list[ChatSummary]:
    return await service.list_chats(current.user_id)


@router.get("/{chat_id}")
async def read_chat(
    chat_id: uuid.UUID, current: CurrentUserDep, service: ChatServiceDep
) -> ChatDetail:
    return await service.get_chat(chat_id, current.user_id)


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(
    chat_id: uuid.UUID, current: CurrentUserDep, service: ChatServiceDep
) -> None:
    await service.delete_chat(chat_id, current.user_id)
