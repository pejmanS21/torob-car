from enums import UserRole
from repositories.admin_user_repository import AdminUserRepository
from repositories.listing_repository import ListingRepository
from schemas.admin import AdminStats
from services.audit_recorder import AuditRecorder

RECENT_AUDIT_LIMIT = 10


class AdminStatsService:
    def __init__(
        self,
        users: AdminUserRepository,
        listings: ListingRepository,
        audit: AuditRecorder,
    ) -> None:
        self._users = users
        self._listings = listings
        self._audit = audit

    async def collect(self) -> AdminStats:
        return AdminStats(
            users_total=await self._users.count(None, None, None),
            users_active=await self._users.count(None, None, True),
            admins_active=await self._users.count(None, UserRole.ADMIN, True),
            listings_total=await self._listings.count(),
            newest_listing_fetched_at=await self._listings.newest_fetched_at(),
            recent_audit=await self._audit.recent(RECENT_AUDIT_LIMIT),
        )
