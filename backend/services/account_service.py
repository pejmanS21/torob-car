"""What an account holds: saved listings and price alerts."""

import json
import uuid
from collections.abc import Sequence
from typing import Any

from errors import AlertNotFoundError, ListingNotFoundError
from models.price_alert import PriceAlert
from repositories.listing_repository import ListingRepository
from repositories.price_alert_repository import PriceAlertRepository
from repositories.saved_listing_repository import SavedListingRepository
from schemas.account import (
    AccountState,
    ImportRequest,
    PriceAlertCreate,
    PriceAlertRead,
)


def _alert_key(title: str, threshold: int, params: dict[str, Any]) -> str:
    return json.dumps([title, threshold, params], sort_keys=True, ensure_ascii=False)


class AccountService:
    def __init__(
        self,
        saved: SavedListingRepository,
        alerts: PriceAlertRepository,
        listings: ListingRepository,
    ) -> None:
        self._saved = saved
        self._alerts = alerts
        self._listings = listings

    async def list_saved(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        return await self._saved.list_listing_ids(user_id)

    async def save_listing(self, user_id: uuid.UUID, listing_id: uuid.UUID) -> None:
        if await self._listings.get_by_id(listing_id) is None:
            raise ListingNotFoundError(listing_id)
        await self._saved.add_many(user_id, [listing_id])

    async def unsave_listing(self, user_id: uuid.UUID, listing_id: uuid.UUID) -> None:
        await self._saved.remove(user_id, listing_id)

    async def list_alerts(self, user_id: uuid.UUID) -> list[PriceAlertRead]:
        alerts = await self._alerts.list_for_user(user_id)
        return [PriceAlertRead.model_validate(alert) for alert in alerts]

    async def create_alert(
        self, user_id: uuid.UUID, payload: PriceAlertCreate
    ) -> PriceAlertRead:
        alert = PriceAlert(user_id=user_id, **payload.model_dump())
        return PriceAlertRead.model_validate(await self._alerts.add(alert))

    async def delete_alert(self, user_id: uuid.UUID, alert_id: uuid.UUID) -> None:
        if not await self._alerts.remove(user_id, alert_id):
            raise AlertNotFoundError(alert_id)

    async def import_state(
        self, user_id: uuid.UUID, payload: ImportRequest
    ) -> AccountState:
        """The one-shot upload of what the browser held before login. Idempotent."""
        await self._import_saved(user_id, payload.saved)
        await self._import_alerts(user_id, payload.alerts)
        return AccountState(
            saved=await self.list_saved(user_id),
            alerts=await self.list_alerts(user_id),
        )

    async def _import_saved(
        self, user_id: uuid.UUID, listing_ids: Sequence[uuid.UUID]
    ) -> None:
        if not listing_ids:
            return
        found = await self._listings.get_by_ids(listing_ids)
        existing = {listing.id for listing in found}
        # dict.fromkeys de-duplicates while keeping the browser's order.
        kept = [item for item in dict.fromkeys(listing_ids) if item in existing]
        await self._saved.add_many(user_id, kept)

    async def _import_alerts(
        self, user_id: uuid.UUID, alerts: Sequence[PriceAlertCreate]
    ) -> None:
        if not alerts:
            return
        stored = await self._alerts.list_for_user(user_id)
        known = {_alert_key(a.title, a.threshold, a.params) for a in stored}
        for alert in alerts:
            key = _alert_key(alert.title, alert.threshold, alert.params)
            if key in known:
                continue
            known.add(key)
            await self._alerts.add(PriceAlert(user_id=user_id, **alert.model_dump()))
