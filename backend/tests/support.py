"""Test doubles shared across the suite."""

from typing import Any

from core.config import Settings

TEST_JWT_SECRET = "t" * 32
TEST_SCRYPT_N = 2**4  # production cost is 2**17 (~0.2 s and 128 MiB per hash)


def fast_auth_settings() -> Settings:
    return Settings(
        _env_file=None,
        env="development",
        jwt_secret=TEST_JWT_SECRET,
        scrypt_n=TEST_SCRYPT_N,
    )


class DictCache:
    """In-memory stand-in for core.cache.Cache (same public methods)."""

    def __init__(self) -> None:
        self.values: dict[str, Any] = {}
        self.data_version = 0
        self.reads = 0

    async def get_json(self, key: str) -> Any | None:
        self.reads += 1
        return self.values.get(key)

    async def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        self.values[key] = value

    async def get_data_version(self) -> int:
        return self.data_version

    async def bump_data_version(self) -> int:
        self.data_version += 1
        return self.data_version

    async def ping(self) -> bool:
        return True
