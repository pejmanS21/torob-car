from fastapi import APIRouter
from sqlalchemy import text

from dependencies.providers import CacheDep, SessionDep
from errors import ServiceUnavailableError

router = APIRouter(tags=["health"])


@router.get("/health")
async def read_liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def read_readiness(session: SessionDep, cache: CacheDep) -> dict[str, str]:
    await session.execute(text("SELECT 1"))  # OperationalError → 503 via errors.py
    if not await cache.ping():
        raise ServiceUnavailableError("Redis unavailable")
    return {"status": "ready"}
