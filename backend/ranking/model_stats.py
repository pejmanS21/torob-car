"""Per-model market summary for GET /models/{model}/stats. Pure Python, no I/O."""

import math
import statistics
import uuid
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

HISTOGRAM_BUCKETS = 8
PERCENTILE_STEPS = 20  # quantiles(n=20) → cut points at every 5 %
LOW_PERCENTILE_INDEX = 0  # 5th percentile
HIGH_PERCENTILE_INDEX = 18  # 95th percentile
MIN_ROWS_FOR_PERCENTILES = 2


@dataclass(frozen=True, slots=True)
class ModelRow:
    listing_id: uuid.UUID
    trim: str
    year: int | None
    price: int | None  # None when missing OR flagged price_suspect
    deal_score: int | None


@dataclass(frozen=True, slots=True)
class HistogramBucket:
    low: int
    high: int
    count: int


@dataclass(frozen=True, slots=True)
class TrimStat:
    trim: str
    count: int
    price_median: int | None


@dataclass(frozen=True, slots=True)
class ModelSummary:
    count: int
    year_min: int | None
    year_max: int | None
    price_median: int | None
    price_min: int | None
    price_max: int | None
    histogram: tuple[HistogramBucket, ...]
    trims: tuple[TrimStat, ...]
    top_deal_ids: tuple[uuid.UUID, ...]


def _percentile_bounds(prices: Sequence[int]) -> tuple[int, int]:
    if len(prices) < MIN_ROWS_FOR_PERCENTILES:
        return prices[0], prices[0]
    cuts = statistics.quantiles(prices, n=PERCENTILE_STEPS)
    return round(cuts[LOW_PERCENTILE_INDEX]), round(cuts[HIGH_PERCENTILE_INDEX])


def _histogram(prices: Sequence[int]) -> tuple[HistogramBucket, ...]:
    """8 equal-width buckets between the 5th and 95th percentile; prices outside
    that range land in the edge buckets, so counts always sum to len(prices)."""
    if not prices:
        return ()
    low, high = _percentile_bounds(prices)
    width = max(1, math.ceil((high - low) / HISTOGRAM_BUCKETS))
    counts = [0] * HISTOGRAM_BUCKETS
    for price in prices:
        index = math.floor((price - low) / width)
        counts[min(HISTOGRAM_BUCKETS - 1, max(0, index))] += 1
    return tuple(
        HistogramBucket(
            low=low + index * width, high=low + (index + 1) * width, count=n
        )
        for index, n in enumerate(counts)
    )


def _trim_stats(rows: Sequence[ModelRow]) -> tuple[TrimStat, ...]:
    counts: dict[str, int] = defaultdict(int)
    prices: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        counts[row.trim] += 1
        if row.price is not None:
            prices[row.trim].append(row.price)
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return tuple(
        TrimStat(
            trim=trim,
            count=count,
            price_median=(
                round(statistics.median(prices[trim])) if prices[trim] else None
            ),
        )
        for trim, count in ordered
    )


def _top_deal_ids(rows: Sequence[ModelRow], limit: int) -> tuple[uuid.UUID, ...]:
    scored = [row for row in rows if row.deal_score is not None]
    scored.sort(key=lambda row: (-row.deal_score, row.listing_id))
    return tuple(row.listing_id for row in scored[:limit])


def summarize_model(rows: Sequence[ModelRow], top_deals: int) -> ModelSummary:
    prices = sorted(row.price for row in rows if row.price is not None)
    years = [row.year for row in rows if row.year is not None]
    return ModelSummary(
        count=len(rows),
        year_min=min(years) if years else None,
        year_max=max(years) if years else None,
        price_median=round(statistics.median(prices)) if prices else None,
        price_min=prices[0] if prices else None,
        price_max=prices[-1] if prices else None,
        histogram=_histogram(prices),
        trims=_trim_stats(rows),
        top_deal_ids=_top_deal_ids(rows, top_deals),
    )
