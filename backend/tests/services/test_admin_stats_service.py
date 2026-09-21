from datetime import UTC, datetime
from unittest.mock import AsyncMock

from enums import UserRole
from repositories.admin_user_repository import AdminUserRepository
from repositories.listing_repository import ListingRepository
from services.admin_stats_service import AdminStatsService
from services.audit_recorder import AuditRecorder


async def test_collect_assembles_counts_from_its_collaborators() -> None:
    users = AsyncMock(spec=AdminUserRepository)
    users.count.side_effect = [5, 4, 1]
    listings = AsyncMock(spec=ListingRepository)
    listings.count.return_value = 100
    fetched_at = datetime.now(UTC)
    listings.newest_fetched_at.return_value = fetched_at
    audit = AsyncMock(spec=AuditRecorder)
    audit.recent.return_value = []
    service = AdminStatsService(users, listings, audit)

    stats = await service.collect()

    users.count.assert_any_await(None, None, None)
    users.count.assert_any_await(None, None, True)
    users.count.assert_any_await(None, UserRole.ADMIN, True)
    audit.recent.assert_awaited_once_with(10)
    assert stats.users_total == 5
    assert stats.users_active == 4
    assert stats.admins_active == 1
    assert stats.listings_total == 100
    assert stats.newest_listing_fetched_at == fetched_at
    assert stats.recent_audit == []
