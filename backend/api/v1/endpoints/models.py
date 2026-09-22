from typing import Annotated

from fastapi import APIRouter, Depends

from dependencies.providers import get_model_stats_service
from schemas.model_stats import ModelStats
from services.model_stats_service import ModelStatsService

router = APIRouter(prefix="/models", tags=["models"])


@router.get("/{model}/stats")
async def read_model_stats(
    service: Annotated[ModelStatsService, Depends(get_model_stats_service)],
    model: str,
) -> ModelStats:
    return await service.get_stats(model)
