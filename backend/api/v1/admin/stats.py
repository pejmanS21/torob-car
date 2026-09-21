from typing import Annotated

from fastapi import APIRouter, Depends

from dependencies.providers import SessionDep, get_audit_recorder
from enums import UserRole
from repositories.admin_user_repository import AdminUserRepository
from repositories.listing_repository import ListingRepository
from schemas.admin import AdminStats
from services.audit_recorder import AuditRecorder

RECENT_AUDIT_LIMIT = 10

router = APIRouter(prefix="/stats")
RecorderDep = Annotated[AuditRecorder, Depends(get_audit_recorder)]


@router.get("")
async def read_stats(session: SessionDep, audit: RecorderDep) -> AdminStats:
    users = AdminUserRepository(session)
    listings = ListingRepository(session)
    return AdminStats(
        users_total=await users.count(None, None, None),
        users_active=await users.count(None, None, True),
        admins_active=await users.count(None, UserRole.ADMIN, True),
        listings_total=await listings.count(),
        newest_listing_fetched_at=await listings.newest_fetched_at(),
        recent_audit=await audit.recent(RECENT_AUDIT_LIMIT),
    )
