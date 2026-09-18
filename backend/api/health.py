from typing import Annotated

from fastapi import APIRouter, Depends

from dependencies.providers import CacheDep, get_health_repository
from errors import ServiceUnavailableError
from repositories.health_repository import HealthRepository

router = APIRouter(tags=["health"])


@router.get("/health")
async def read_liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def read_readiness(
    database: Annotated[HealthRepository, Depends(get_health_repository)],
    cache: CacheDep,
) -> dict[str, str]:
    await database.ping()  # OperationalError → 503 via errors.py
    if not await cache.ping():
        raise ServiceUnavailableError("Redis unavailable")
    return {"status": "ready"}
