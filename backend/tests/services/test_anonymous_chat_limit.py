from datetime import timedelta
from unittest.mock import AsyncMock

import pytest

from errors import AnonymousChatLimitError
from models.user import utc_now
from repositories.anonymous_chat_quota_repository import QuotaReservation
from services.anonymous_chat_limit import AnonymousChatLimit
from tests.support import fast_auth_settings


async def test_exhausted_quota_reports_sign_in_and_reset_time() -> None:
    quotas = AsyncMock()
    quotas.reserve.return_value = QuotaReservation(
        False, utc_now() + timedelta(hours=1)
    )
    limit = AnonymousChatLimit(quotas, fast_auth_settings())
    with pytest.raises(AnonymousChatLimitError) as caught:
        await limit.enforce("192.0.2.1")
    assert caught.value.context["limit"] == 3
    assert 3599 <= caught.value.context["retry_after_seconds"] <= 3600


async def test_identity_is_stable_private_and_independent_per_address() -> None:
    quotas = AsyncMock()
    quotas.reserve.return_value = QuotaReservation(True, utc_now() + timedelta(days=1))
    limit = AnonymousChatLimit(quotas, fast_auth_settings())
    for address in ("192.0.2.1", "192.0.2.1", "192.0.2.2"):
        await limit.enforce(address)
    identities = [call.args[0] for call in quotas.reserve.call_args_list]
    assert identities[0] == identities[1] != identities[2]
    assert all(
        len(identity) == 64 and "192.0.2" not in identity for identity in identities
    )
