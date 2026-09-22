"""Anonymous quota shared by all workers, keyed by the trusted client address."""

import hashlib
import hmac
import math
from datetime import timedelta

from core.config import Settings
from errors import AnonymousChatLimitError
from models.user import utc_now
from repositories.anonymous_chat_quota_repository import AnonymousChatQuotaRepository

DAY_SECONDS = 86_400


class AnonymousChatLimit:
    def __init__(
        self, quotas: AnonymousChatQuotaRepository, settings: Settings
    ) -> None:
        self._quotas = quotas
        self._settings = settings

    async def enforce(self, client_host: str) -> None:
        # Store a keyed digest, never the raw IP. ASGI handles trusted proxy headers.
        identity = hmac.new(
            self._settings.jwt_secret.get_secret_value().encode(),
            client_host.encode(),
            hashlib.sha256,
        ).hexdigest()
        now = utc_now()
        reservation = await self._quotas.reserve(
            identity,
            self._settings.anonymous_chat_daily_limit,
            now,
            now + timedelta(seconds=DAY_SECONDS),
        )
        if not reservation.allowed:
            retry_after = max(
                1, math.ceil((reservation.resets_at - now).total_seconds())
            )
            raise AnonymousChatLimitError(
                self._settings.anonymous_chat_daily_limit, retry_after
            )
