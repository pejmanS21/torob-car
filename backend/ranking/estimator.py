"""Comparables-based price estimate and deal score. Pure Python, no I/O (spec §6.3)."""

import statistics
import uuid
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from enums import BodyCondition, Category, EstimateBasis

MIN_COMPARABLES = 5
NEAR_YEAR_SPAN = 1
FAR_YEAR_SPAN = 2
KM_WEIGHT = 0.08
KM_RATIO_FLOOR = -0.5
KM_RATIO_CEILING = 1.0
INSURANCE_NEUTRAL_MONTHS = 6
INSURANCE_WEIGHT_PER_MONTH = 0.002
DEAL_BASELINE = 72
# ponytail: slope fitted to the real price spread (IQR about -10%..+12%). The
# frontend's 2.4 saturates 25% of scores at the clamp; 1.0 saturates under 5%.
DEAL_DIFF_WEIGHT = 1.0
DEAL_KM_WEIGHT = 120
DEAL_BODY_WEIGHT = 90
DEAL_BODY_NEUTRAL = 0.92
DEAL_SCORE_MIN = 5
DEAL_SCORE_MAX = 99
CATCH_ALL_MARKER = "سایر"
# Beyond these bounds the listed price is a deposit, a typo or a placeholder, not a
# deal: 6.6% of cars and 22% of motorcycles in the first scrape.
SUSPECT_BELOW_PCT = -40.0
SUSPECT_ABOVE_PCT = 100.0
ESTIMATED_CATEGORIES = frozenset({Category.LIGHT, Category.MOTORCYCLE})

# Mirrors frontend/src/lib/catalog.ts BODIES where an equivalent exists.
BODY_FACTORS: Mapping[BodyCondition, float] = {
    BodyCondition.INTACT: 1.0,
    BodyCondition.NO_PAINT: 1.0,
    BodyCondition.ORIGINAL: 1.0,
    BodyCondition.MINOR_SCRATCHES: 0.98,
    BodyCondition.PARTIAL_PAINT: 0.94,
    BodyCondition.RESTORED: 0.9,
    BodyCondition.DROPPED: 0.85,
    BodyCondition.HEAVY_PAINT: 0.82,
    BodyCondition.ACCIDENT: 0.72,
}

type GroupKey = tuple[Category, str, int]


@dataclass(frozen=True, slots=True)
class EstimatorInput:
    listing_id: uuid.UUID
    category: Category
    trim: str | None
    model: str | None
    year: int | None
    km: int | None
    price: int | None
    insurance_months: int | None
    body_condition: BodyCondition | None


@dataclass(frozen=True, slots=True)
class Estimate:
    listing_id: uuid.UUID
    est_price: int | None
    est_basis: EstimateBasis
    est_sample_size: int
    km_factor: float
    insurance_factor: float
    diff_pct: float | None
    deal_score: int | None
    price_suspect: bool = False


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _is_comparable(row: EstimatorInput) -> bool:
    return (
        row.category in ESTIMATED_CATEGORIES
        and row.price is not None
        and row.year is not None
        and row.trim is not None
        and row.model is not None
        and CATCH_ALL_MARKER not in row.trim
    )


class PriceEstimator:
    def __init__(self, rows: Sequence[EstimatorInput], current_year: int) -> None:
        self._rows = rows
        self._current_year = current_year
        self._by_trim: dict[GroupKey, list[int]] = defaultdict(list)
        self._by_model: dict[GroupKey, list[int]] = defaultdict(list)
        self._expected_km = self._build_expected_km(rows)
        for row in filter(_is_comparable, rows):
            self._by_trim[(row.category, row.trim, row.year)].append(row.price)
            self._by_model[(row.category, row.model, row.year)].append(row.price)

    def estimate_all(self) -> list[Estimate]:
        return [self._estimate(row) for row in self._rows]

    def _build_expected_km(
        self, rows: Iterable[EstimatorInput]
    ) -> dict[tuple[Category, int], float]:
        by_age: dict[tuple[Category, int], list[int]] = defaultdict(list)
        for row in rows:
            if row.km is not None and row.year is not None:
                by_age[(row.category, self._current_year - row.year)].append(row.km)
        return {
            key: statistics.median(values)
            for key, values in by_age.items()
            if len(values) >= MIN_COMPARABLES
        }

    def _estimate(self, row: EstimatorInput) -> Estimate:
        km_factor = self._km_factor(row)
        insurance_factor = self._insurance_factor(row)
        base, basis, sample_size = self._base_price(row)
        if base is None or row.price is None:
            return self._no_estimate(row, km_factor, insurance_factor)
        est_price = base * km_factor * insurance_factor
        diff_pct = (row.price - est_price) / est_price * 100
        suspect = not SUSPECT_BELOW_PCT <= diff_pct <= SUSPECT_ABOVE_PCT
        score = (
            None
            if suspect
            else self._deal_score(diff_pct, km_factor, row.body_condition)
        )
        return Estimate(
            listing_id=row.listing_id,
            est_price=round(est_price),
            est_basis=basis,
            est_sample_size=sample_size,
            km_factor=km_factor,
            insurance_factor=insurance_factor,
            diff_pct=None if suspect else round(diff_pct, 1),
            deal_score=score,
            price_suspect=suspect,
        )

    @staticmethod
    def _no_estimate(
        row: EstimatorInput, km_factor: float, insurance_factor: float
    ) -> Estimate:
        return Estimate(
            listing_id=row.listing_id,
            est_price=None,
            est_basis=EstimateBasis.NONE,
            est_sample_size=0,
            km_factor=km_factor,
            insurance_factor=insurance_factor,
            diff_pct=None,
            deal_score=None,
        )

    def _base_price(
        self, row: EstimatorInput
    ) -> tuple[float | None, EstimateBasis, int]:
        if not _is_comparable(row):
            return None, EstimateBasis.NONE, 0
        attempts = (
            (self._by_trim, row.trim, 0, EstimateBasis.TRIM_YEAR),
            (self._by_trim, row.trim, NEAR_YEAR_SPAN, EstimateBasis.TRIM_NEAR_YEAR),
            (self._by_model, row.model, 0, EstimateBasis.MODEL_YEAR),
            (self._by_model, row.model, FAR_YEAR_SPAN, EstimateBasis.MODEL_NEAR_YEAR),
        )
        for groups, name, span, basis in attempts:
            prices = self._comparables(groups, row, name, span)
            if len(prices) >= MIN_COMPARABLES:
                return statistics.median(prices), basis, len(prices)
        return None, EstimateBasis.NONE, 0

    def _comparables(
        self,
        groups: Mapping[GroupKey, list[int]],
        row: EstimatorInput,
        name: str,
        span: int,
    ) -> list[int]:
        prices: list[int] = []
        for year in range(row.year - span, row.year + span + 1):
            prices.extend(groups.get((row.category, name, year), ()))
        prices.remove(row.price)  # leave-one-out: a listing never validates itself
        return prices

    def _km_factor(self, row: EstimatorInput) -> float:
        if row.km is None or row.year is None:
            return 1.0
        expected = self._expected_km.get((row.category, self._current_year - row.year))
        if not expected:
            return 1.0
        ratio = _clamp((row.km - expected) / expected, KM_RATIO_FLOOR, KM_RATIO_CEILING)
        return 1 - ratio * KM_WEIGHT

    @staticmethod
    def _insurance_factor(row: EstimatorInput) -> float:
        if row.insurance_months is None:
            return 1.0
        months_over_neutral = row.insurance_months - INSURANCE_NEUTRAL_MONTHS
        return 1 + months_over_neutral * INSURANCE_WEIGHT_PER_MONTH

    @staticmethod
    def _deal_score(
        diff_pct: float, km_factor: float, body: BodyCondition | None
    ) -> int:
        body_term = (
            DEAL_BODY_WEIGHT * (BODY_FACTORS[body] - DEAL_BODY_NEUTRAL) if body else 0.0
        )
        raw = (
            DEAL_BASELINE
            - DEAL_DIFF_WEIGHT * diff_pct
            + DEAL_KM_WEIGHT * (km_factor - 1)
            + body_term
        )
        return round(_clamp(raw, DEAL_SCORE_MIN, DEAL_SCORE_MAX))
