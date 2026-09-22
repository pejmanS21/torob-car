from typing import Annotated

from fastapi import APIRouter, Depends

from dependencies.providers import get_estimate_service
from schemas.estimate import EstimateRequest, EstimateResponse
from services.estimate_service import EstimateService

router = APIRouter(prefix="/estimates", tags=["estimates"])


@router.post("")
async def create_estimate(
    service: Annotated[EstimateService, Depends(get_estimate_service)],
    request: EstimateRequest,
) -> EstimateResponse:
    return await service.estimate(request)
