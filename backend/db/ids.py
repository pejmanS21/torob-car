import time
import uuid

_TIMESTAMP_MASK = 0xFFFFFFFFFFFF
_NANOSECONDS_PER_MILLISECOND = 1_000_000


def new_uuid8() -> uuid.UUID:
    """Time-ordered UUIDv8: a 48-bit millisecond timestamp in the leading field,
    pseudo-random in the rest. Keeps index locality while staying inside the
    application-defined v8 space."""
    timestamp_ms = (time.time_ns() // _NANOSECONDS_PER_MILLISECOND) & _TIMESTAMP_MASK
    return uuid.uuid8(a=timestamp_ms)
