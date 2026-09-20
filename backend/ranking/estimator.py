"""Comparables-based price estimate and deal score. Pure Python, no I/O (spec §6.3).

Two entry points share every formula: `estimate_all()` is the ingest bulk pass
(leave-one-out per listing) and `estimate_for()` answers a single POST /estimates
query (spec 3 §3.3)."""

import statistics
import uuid
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from enums import BodyCondition, Category, EstimateBasis, Source

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
QUARTILES = 4
LOWER_QUARTILE_INDEX = 0
UPPER_QUARTILE_INDEX = 2

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
type Groups = Mapping[GroupKey, list[int]]


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
    source: Source = Source.DIVAR


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


@dataclass(frozen=True, slots=True)
class EstimateQuery:
    """One hypothetical vehicle, as posted to /estimates (no listing of its own)."""

    category: Category
    trim: str
    model: str
    year: int
    km: int | None
    insurance_months: int | None


@dataclass(frozen=True, slots=True)
class SingleEstimate:
    base: int | None
    est_price: int | None
    low: int | None
    high: int | None
    est_basis: EstimateBasis
    est_sample_size: int
    km_factor: float
    insurance_factor: float
    tried: tuple[EstimateBasis, ...]  # the basis chain, for the 422 details


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _is_baseline(row: EstimatorInput) -> bool:
    """Divar is the market: it is the deepest, most ordinary pool of private ads.
    The inspected-and-warranted marketplaces sell at a premium, so letting them set
    the baseline would quietly re-price every Divar listing against their markup.
    Ads from every source are still scored — they are just scored against Divar."""
    return _is_comparable(row) and row.source is Source.DIVAR


def _is_comparable(row: EstimatorInput) -> bool:
    return (
        row.category in ESTIMATED_CATEGORIES
        and row.price is not None
        and row.year is not None
        and row.trim is not None
        and row.model is not None
        and CATCH_ALL_MARKER not in row.trim
    )


def insurance_factor_of(insurance_months: int | None) -> float:
    if insurance_months is None:
        return 1.0
    months_over_neutral = insurance_months - INSURANCE_NEUTRAL_MONTHS
    return 1 + months_over_neutral * INSURANCE_WEIGHT_PER_MONTH


def km_factor_of(km: int | None, expected_km: float | None) -> float:
    if km is None or not expected_km:
        return 1.0
    ratio = _clamp((km - expected_km) / expected_km, KM_RATIO_FLOOR, KM_RATIO_CEILING)
    return 1 - ratio * KM_WEIGHT


class PriceEstimator:
    def __init__(self, rows: Sequence[EstimatorInput], current_year: int) -> None:
        self._rows = rows
        self._current_year = current_year
        self._by_trim: dict[GroupKey, list[int]] = defaultdict(list)
        self._by_model: dict[GroupKey, list[int]] = defaultdict(list)
        self._expected_km = self._build_expected_km(rows)
        for row in filter(_is_baseline, rows):
            self._by_trim[(row.category, row.trim, row.year)].append(row.price)
            self._by_model[(row.category, row.model, row.year)].append(row.price)

    def estimate_all(self) -> list[Estimate]:
        return [self._estimate(row) for row in self._rows]

    def estimate_for(self, query: EstimateQuery) -> SingleEstimate:
        """The bulk formulas applied to a vehicle that is not in the data set, so
        nothing is left out. `est_price is None` means no basis had enough
        comparables; `tried` lists the chain for the caller's error details."""
        km_factor = self._km_factor_of(query.category, query.year, query.km)
        insurance_factor = insurance_factor_of(query.insurance_months)
        tried: list[EstimateBasis] = []
        for groups, name, span, basis in self._attempts(query.trim, query.model):
            tried.append(basis)
            prices = self._collect(groups, query.category, name, query.year, span)
            if len(prices) >= MIN_COMPARABLES:
                return self._single(prices, basis, km_factor, insurance_factor, tried)
        return SingleEstimate(
            base=None,
            est_price=None,
            low=None,
            high=None,
            est_basis=EstimateBasis.NONE,
            est_sample_size=0,
            km_factor=km_factor,
            insurance_factor=insurance_factor,
            tried=tuple(tried),
        )

    @staticmethod
    def _single(
        prices: list[int],
        basis: EstimateBasis,
        km_factor: float,
        insurance_factor: float,
        tried: list[EstimateBasis],
    ) -> SingleEstimate:
        scale = km_factor * insurance_factor
        quartiles = statistics.quantiles(prices, n=QUARTILES)
        return SingleEstimate(
            base=round(statistics.median(prices)),
            est_price=round(statistics.median(prices) * scale),
            low=round(quartiles[LOWER_QUARTILE_INDEX] * scale),
            high=round(quartiles[UPPER_QUARTILE_INDEX] * scale),
            est_basis=basis,
            est_sample_size=len(prices),
            km_factor=km_factor,
            insurance_factor=insurance_factor,
            tried=tuple(tried),
        )

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
        km_factor = self._km_factor_of(row.category, row.year, row.km)
        insurance_factor = insurance_factor_of(row.insurance_months)
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

    def _attempts(
        self, trim: str, model: str
    ) -> tuple[tuple[Groups, str, int, EstimateBasis], ...]:
        """The basis chain, most specific first (spec §6.3)."""
        return (
            (self._by_trim, trim, 0, EstimateBasis.TRIM_YEAR),
            (self._by_trim, trim, NEAR_YEAR_SPAN, EstimateBasis.TRIM_NEAR_YEAR),
            (self._by_model, model, 0, EstimateBasis.MODEL_YEAR),
            (self._by_model, model, FAR_YEAR_SPAN, EstimateBasis.MODEL_NEAR_YEAR),
        )

    def _base_price(
        self, row: EstimatorInput
    ) -> tuple[float | None, EstimateBasis, int]:
        if not _is_comparable(row):
            return None, EstimateBasis.NONE, 0
        for groups, name, span, basis in self._attempts(row.trim, row.model):
            prices = self._collect(groups, row.category, name, row.year, span)
            if _is_baseline(row):
                # Leave-one-out: a listing never validates itself. Only rows that fed
                # the baseline are in there to remove.
                prices.remove(row.price)
            if len(prices) >= MIN_COMPARABLES:
                return statistics.median(prices), basis, len(prices)
        return None, EstimateBasis.NONE, 0

    @staticmethod
    def _collect(
        groups: Groups, category: Category, name: str, year: int, span: int
    ) -> list[int]:
        prices: list[int] = []
        for candidate_year in range(year - span, year + span + 1):
            prices.extend(groups.get((category, name, candidate_year), ()))
        return prices

    def _km_factor_of(
        self, category: Category, year: int | None, km: int | None
    ) -> float:
        if year is None:
            return 1.0
        expected = self._expected_km.get((category, self._current_year - year))
        return km_factor_of(km, expected)

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
