import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from core.cache import DATA_VERSION_KEY, Cache


class FakeRedis:
    def __init__(self, *, down: bool = False) -> None:
        self.store: dict[str, str] = {}
        self.down = down

    def _check(self) -> None:
        if self.down:
            raise RedisConnectionError("redis is down")

    async def get(self, key: str) -> str | None:
        self._check()
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int) -> None:
        self._check()
        self.store[key] = value

    async def incr(self, key: str) -> int:
        self._check()
        self.store[key] = str(int(self.store.get(key, "0")) + 1)
        return int(self.store[key])

    async def ping(self) -> bool:
        self._check()
        return True


async def test_json_round_trip_keeps_persian_text() -> None:
    cache = Cache(FakeRedis())
    await cache.set_json("key", {"chips": ["پژو ۲۰۶"]}, ttl_seconds=60)
    assert await cache.get_json("key") == {"chips": ["پژو ۲۰۶"]}
    assert await cache.get_json("missing") is None


async def test_data_version_starts_at_zero_and_increments() -> None:
    redis = FakeRedis()
    cache = Cache(redis)
    assert await cache.get_data_version() == 0
    assert await cache.bump_data_version() == 1
    assert redis.store[DATA_VERSION_KEY] == "1"


async def test_an_outage_reads_as_a_miss_and_never_raises() -> None:
    cache = Cache(FakeRedis(down=True))
    assert await cache.get_json("key") is None
    await cache.set_json("key", {"a": 1}, ttl_seconds=60)
    assert await cache.get_data_version() == 0
    assert await cache.ping() is False


async def test_ping_during_an_outage_logs_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level("WARNING", logger="core.cache"):
        assert await Cache(FakeRedis(down=True)).ping() is False
    assert any("cache ping failed" in record.getMessage() for record in caplog.records)


async def test_bumping_the_version_during_an_outage_fails_loudly() -> None:
    with pytest.raises(RedisConnectionError):
        await Cache(FakeRedis(down=True)).bump_data_version()
