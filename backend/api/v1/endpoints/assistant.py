from typing import Annotated

from fastapi import APIRouter, Depends

from dependencies.providers import get_assistant_service
from schemas.assistant import AssistantRequest, AssistantResponse
from services.assistant_service import AssistantService

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("", response_model=AssistantResponse)
async def ask_assistant(
    service: Annotated[AssistantService, Depends(get_assistant_service)],
    request: AssistantRequest,
) -> AssistantResponse:
    return await service.reply(request)
