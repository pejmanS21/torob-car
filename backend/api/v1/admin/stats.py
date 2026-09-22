from typing import Annotated

from fastapi import APIRouter, Depends

from dependencies.providers import get_admin_stats_service
from schemas.admin import AdminStats
from services.admin_stats_service import AdminStatsService

router = APIRouter(prefix="/stats")
ServiceDep = Annotated[AdminStatsService, Depends(get_admin_stats_service)]


@router.get("")
async def read_stats(service: ServiceDep) -> AdminStats:
    return await service.collect()
