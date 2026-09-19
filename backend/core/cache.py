"""Thin async Redis wrapper. The cache is an optimisation, never a dependency:
when Redis is unreachable every method logs a WARNING and behaves like a miss, so
search keeps working uncached (spec §7.5). This is the one deliberate place where a
connection error is not re-raised."""

import json
import logging
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

DATA_VERSION_KEY = "search:data_version"


class Cache:
    def __init__(self, client: Redis) -> None:
        self._client = client

    async def get_json(self, key: str) -> Any | None:
        try:
            raw = await self._client.get(key)
        except RedisError as error:
            logger.warning("cache read failed", extra={"fields": {"error": str(error)}})
            return None
        return None if raw is None else json.loads(raw)

    async def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        try:
            await self._client.set(key, json.dumps(value), ex=ttl_seconds)
        except RedisError as error:
            logger.warning(
                "cache write failed", extra={"fields": {"error": str(error)}}
            )

    async def get_data_version(self) -> int:
        try:
            raw = await self._client.get(DATA_VERSION_KEY)
        except RedisError as error:
            logger.warning("cache read failed", extra={"fields": {"error": str(error)}})
            return 0
        return int(raw) if raw is not None else 0

    async def bump_data_version(self) -> int:
        """Invalidates every search and facet key at once. Raises on failure: a
        re-ingest that cannot invalidate the cache must not look successful."""
        return int(await self._client.incr(DATA_VERSION_KEY))

    async def ping(self) -> bool:
        try:
            return bool(await self._client.ping())
        except RedisError as error:
            logger.warning("cache ping failed", extra={"fields": {"error": str(error)}})
            return False

    async def close(self) -> None:
        await self._client.aclose()
