import uuid

import pytest

from enums import BodyCondition, Category, EstimateBasis
from ranking.estimator import EstimateQuery, EstimatorInput, PriceEstimator

CURRENT_YEAR = 1405
TRIM = "پژو 206 تیپ ۲"
MODEL = "پژو 206"


def make_row(price: int | None, **overrides: object) -> EstimatorInput:
    fields: dict[str, object] = {
        "listing_id": uuid.uuid4(),
        "category": Category.LIGHT,
        "trim": TRIM,
        "model": MODEL,
        "year": 1398,
        "km": None,
        "price": price,
        "insurance_months": None,
        "body_condition": None,
    }
    return EstimatorInput(**{**fields, **overrides})


def estimate_first(rows: list[EstimatorInput]) -> object:
    return PriceEstimator(rows, CURRENT_YEAR).estimate_all()[0]


def test_trim_year_median_excludes_the_listing_itself() -> None:
    target = make_row(900)
    peers = [make_row(price) for price in (700, 750, 800, 850, 1000)]
    estimate = estimate_first([target, *peers])
    assert estimate.est_basis is EstimateBasis.TRIM_YEAR
    assert estimate.est_sample_size == 5
    assert estimate.est_price == 800  # median of the five peers, not of all six


def test_falls_back_to_neighbouring_years_of_the_same_trim() -> None:
    target = make_row(800)
    peers = [make_row(800, year=year) for year in (1397, 1397, 1397, 1399, 1399)]
    assert estimate_first([target, *peers]).est_basis is EstimateBasis.TRIM_NEAR_YEAR


def test_falls_back_to_the_model_when_the_trim_is_thin() -> None:
    target = make_row(800)
    peers = [make_row(800, trim=f"پژو 206 تیپ {number}") for number in range(3, 8)]
    assert estimate_first([target, *peers]).est_basis is EstimateBasis.MODEL_YEAR


def test_no_estimate_without_enough_comparables() -> None:
    estimate = estimate_first([make_row(800), make_row(810)])
    assert estimate.est_basis is EstimateBasis.NONE
    assert estimate.est_price is None
    assert estimate.deal_score is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"category": Category.HEAVY},
        {"trim": "اسکوتر(سایر)"},
        {"price": None},
        {"year": None},
    ],
)
def test_rows_that_cannot_be_compared_get_no_estimate(overrides: dict) -> None:
    target = make_row(**{"price": 800, **overrides})
    shared = {key: value for key, value in overrides.items() if key != "price"}
    peers = [make_row(800, **shared) for _ in range(6)]
    assert estimate_first([target, *peers]).est_basis is EstimateBasis.NONE


def test_high_mileage_lowers_the_estimate_and_low_mileage_raises_it() -> None:
    peers = [make_row(800, km=100_000) for _ in range(6)]
    tired = estimate_first([make_row(800, km=200_000), *peers])
    fresh = estimate_first([make_row(800, km=50_000), *peers])
    assert tired.km_factor == pytest.approx(0.92)  # ratio clamped to +1.0
    assert fresh.km_factor == pytest.approx(1.04)  # ratio clamped to -0.5
    assert tired.est_price < 800 < fresh.est_price


def test_insurance_months_adjust_the_estimate() -> None:
    peers = [make_row(800) for _ in range(5)]
    estimate = estimate_first([make_row(800, insurance_months=12), *peers])
    assert estimate.insurance_factor == pytest.approx(1.012)


def test_cheaper_than_estimate_scores_higher() -> None:
    peers = [make_row(1000) for _ in range(5)]
    cheap = estimate_first([make_row(900), *peers])
    pricey = estimate_first([make_row(1100), *peers])
    assert cheap.diff_pct == pytest.approx(-10.0)
    assert cheap.deal_score == 82 and pricey.deal_score == 62


def test_body_condition_moves_the_deal_score_only_when_known() -> None:
    peers = [make_row(1000) for _ in range(5)]
    unknown = estimate_first([make_row(1000), *peers])
    crashed = estimate_first(
        [make_row(1000, body_condition=BodyCondition.ACCIDENT), *peers]
    )
    assert unknown.deal_score == 72
    assert crashed.deal_score == 54  # 72 + 90 * (0.72 - 0.92)


@pytest.mark.parametrize("price", [10, 590, 2100])
def test_implausible_price_is_flagged_not_rewarded(price: int) -> None:
    peers = [make_row(1000) for _ in range(5)]
    estimate = estimate_first([make_row(price), *peers])
    assert estimate.price_suspect is True
    assert estimate.deal_score is None and estimate.diff_pct is None
    assert estimate.est_price == 1000  # the estimate itself is still reported


def test_single_estimate_uses_the_same_formulas_as_the_bulk_pass() -> None:
    peers = [make_row(800, km=100_000, insurance_months=12) for _ in range(6)]
    target = make_row(900, km=150_000, insurance_months=12)
    estimator = PriceEstimator([target, *peers], CURRENT_YEAR)
    bulk = estimator.estimate_all()[0]
    single = estimator.estimate_for(
        EstimateQuery(
            category=Category.LIGHT,
            trim=TRIM,
            model=MODEL,
            year=1398,
            km=150_000,
            insurance_months=12,
        )
    )
    assert single.est_basis is EstimateBasis.TRIM_YEAR
    assert single.km_factor == bulk.km_factor
    assert single.insurance_factor == bulk.insurance_factor
    assert single.base == 800  # median of all seven prices, nothing left out
    assert single.est_price == round(800 * single.km_factor * single.insurance_factor)
    assert single.low <= single.est_price <= single.high
    assert single.est_sample_size == 7


def test_single_estimate_reports_the_basis_chain_when_nothing_matches() -> None:
    estimator = PriceEstimator([make_row(800)], CURRENT_YEAR)
    single = estimator.estimate_for(
        EstimateQuery(
            category=Category.LIGHT,
            trim="ناشناخته",
            model="ناشناخته",
            year=1398,
            km=None,
            insurance_months=None,
        )
    )
    assert single.est_price is None and single.low is None
    assert single.tried == (
        EstimateBasis.TRIM_YEAR,
        EstimateBasis.TRIM_NEAR_YEAR,
        EstimateBasis.MODEL_YEAR,
        EstimateBasis.MODEL_NEAR_YEAR,
    )


def test_single_estimate_range_is_the_interquartile_band() -> None:
    peers = [make_row(price) for price in (700, 750, 800, 850, 1000)]
    single = PriceEstimator(peers, CURRENT_YEAR).estimate_for(
        EstimateQuery(
            category=Category.LIGHT,
            trim=TRIM,
            model=MODEL,
            year=1398,
            km=None,
            insurance_months=None,
        )
    )
    assert (single.low, single.est_price, single.high) == (725, 800, 925)
