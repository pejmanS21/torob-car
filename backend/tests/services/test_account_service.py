import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from errors import AlertNotFoundError, ListingNotFoundError
from models.price_alert import PriceAlert
from repositories.listing_repository import ListingRepository
from repositories.price_alert_repository import PriceAlertRepository
from repositories.saved_listing_repository import SavedListingRepository
from schemas.account import ImportRequest, PriceAlertCreate
from services.account_service import AccountService

USER_ID = uuid.UUID(int=1)
REAL = uuid.UUID(int=100)
GONE = uuid.UUID(int=200)
ALERT = {"title": "۲۰۶ زیر ۵۰۰", "threshold": 500_000_000, "params": {"q": "۲۰۶"}}


def _stored(alert: PriceAlert) -> PriceAlert:
    alert.id = uuid.uuid4()
    alert.created_at = datetime.now(UTC)
    return alert


class Doubles:
    def __init__(self) -> None:
        self.saved = AsyncMock(spec=SavedListingRepository)
        self.alerts = AsyncMock(spec=PriceAlertRepository)
        self.listings = AsyncMock(spec=ListingRepository)
        self.alerts.add.side_effect = _stored
        self.alerts.list_for_user.return_value = []
        self.saved.list_listing_ids.return_value = []
        self.service = AccountService(self.saved, self.alerts, self.listings)


async def test_saving_an_unknown_listing_raises() -> None:
    doubles = Doubles()
    doubles.listings.get_by_id.return_value = None
    with pytest.raises(ListingNotFoundError):
        await doubles.service.save_listing(USER_ID, GONE)
    doubles.saved.add_many.assert_not_awaited()


async def test_saving_a_known_listing_stores_it() -> None:
    doubles = Doubles()
    doubles.listings.get_by_id.return_value = SimpleNamespace(id=REAL)
    await doubles.service.save_listing(USER_ID, REAL)
    doubles.saved.add_many.assert_awaited_once_with(USER_ID, [REAL])


async def test_create_alert_belongs_to_the_caller() -> None:
    doubles = Doubles()
    created = await doubles.service.create_alert(USER_ID, PriceAlertCreate(**ALERT))
    assert doubles.alerts.add.call_args.args[0].user_id == USER_ID
    assert (created.title, created.threshold, created.params) == (
        ALERT["title"],
        ALERT["threshold"],
        ALERT["params"],
    )


async def test_deleting_a_missing_or_foreign_alert_raises() -> None:
    doubles = Doubles()
    doubles.alerts.remove.return_value = False
    with pytest.raises(AlertNotFoundError):
        await doubles.service.delete_alert(USER_ID, uuid.UUID(int=9))


async def test_import_skips_vanished_listings_and_duplicate_alerts() -> None:
    doubles = Doubles()
    doubles.listings.get_by_ids.return_value = [SimpleNamespace(id=REAL)]
    payload = ImportRequest(saved=[REAL, GONE, REAL], alerts=[ALERT, ALERT])
    await doubles.service.import_state(USER_ID, payload)
    doubles.saved.add_many.assert_awaited_once_with(USER_ID, [REAL])
    assert doubles.alerts.add.await_count == 1


async def test_import_does_not_duplicate_an_alert_the_server_already_has() -> None:
    doubles = Doubles()
    doubles.listings.get_by_ids.return_value = []
    existing = _stored(PriceAlert(user_id=USER_ID, **ALERT))
    doubles.alerts.list_for_user.return_value = [existing]
    state = await doubles.service.import_state(
        USER_ID, ImportRequest(saved=[], alerts=[ALERT])
    )
    doubles.alerts.add.assert_not_awaited()
    assert [alert.id for alert in state.alerts] == [existing.id]


async def test_an_empty_import_touches_nothing() -> None:
    doubles = Doubles()
    await doubles.service.import_state(USER_ID, ImportRequest(saved=[], alerts=[]))
    doubles.listings.get_by_ids.assert_not_awaited()
    doubles.alerts.add.assert_not_awaited()


def test_import_limits_and_alert_bounds_are_enforced() -> None:
    with pytest.raises(ValidationError):
        ImportRequest(saved=[uuid.uuid4() for _ in range(501)], alerts=[])
    with pytest.raises(ValidationError):
        ImportRequest(saved=[], alerts=[ALERT] * 51)
    with pytest.raises(ValidationError):
        PriceAlertCreate(title="", threshold=1, params={})
    with pytest.raises(ValidationError):
        PriceAlertCreate(title="x", threshold=0, params={})
