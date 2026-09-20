import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from enums import Fuel, Gearbox, MentionLevel, SortKey
from ranking import labels
from ranking.ranker import ListingRanker
from ranking.types import Candidate, RankingQuery, ResolvedCity, VehicleTarget

NOW = datetime(2026, 9, 17, 20, 0, tzinfo=UTC)
TEHRAN = ResolvedCity("تهران", 35.70, 51.40)
MILLION = 1_000_000
TRIM_2 = "پژو 206 تیپ ۲"
TRIM_5 = "پژو 206 تیپ ۵"

QUERY = RankingQuery(
    targets=(VehicleTarget(MentionLevel.TRIM, "پژو", "پژو 206", TRIM_2),),
    year_min=1398,
    year_max=1398,
    price_max=800 * MILLION,
    km_max=100_000,
    cities=(TEHRAN,),
    gearbox=Gearbox.MANUAL,
)
EXACT_MATCH = Candidate(
    id=uuid.UUID(int=1),
    brand="پژو",
    model="پژو 206",
    trim=TRIM_2,
    year=1398,
    km=60_000,
    price=780 * MILLION,
    city="تهران",
    lat=35.72,
    lng=51.42,
    gearbox=Gearbox.MANUAL,
    fuel=Fuel.PETROL,
    color="سفید",
    deal_score=70,
    posted_at=NOW - timedelta(hours=3),
)


def rank(query: RankingQuery, *candidates: Candidate) -> list:
    return ListingRanker().rank(query, candidates, NOW)


def variant(number: int, **changes: object) -> Candidate:
    return replace(EXACT_MATCH, id=uuid.UUID(int=number), **changes)


def test_exact_match_scores_full_match_and_has_no_labels() -> None:
    (result,) = rank(QUERY, EXACT_MATCH)
    assert result.match == 1.0
    assert result.is_exact is True
    assert result.labels == ()


DEGRADATIONS = {
    "older": {"year": 1397},
    "over_budget": {"price": 850 * MILLION},
    "other_trim": {"trim": TRIM_5},
    "karaj": {"city": "کرج", "lat": 35.83, "lng": 50.97},
    "high_km": {"km": 130_000},
    "automatic": {"gearbox": Gearbox.AUTOMATIC},
}


@pytest.mark.parametrize("changes", DEGRADATIONS.values(), ids=DEGRADATIONS.keys())
def test_degrading_any_single_criterion_never_raises_the_rank(changes: dict) -> None:
    results = rank(QUERY, variant(2, **changes), EXACT_MATCH)
    assert [result.id for result in results] == [EXACT_MATCH.id, uuid.UUID(int=2)]
    assert results[1].is_exact is False
    assert results[1].match < 1.0


def test_near_miss_labels_explain_the_two_biggest_gaps() -> None:
    near_miss = variant(2, year=1397, price=820 * MILLION, color="مشکی")
    (result,) = rank(QUERY, near_miss)
    # year costs 2.0 x 0.2 = 0.40 of weighted closeness, price only 2.5 x 0.1 = 0.25
    assert result.labels == ("یک سال قدیمی‌تر", "۲۰ میلیون بالاتر از بودجه")


def test_nearer_city_outranks_a_far_one() -> None:
    karaj = variant(2, city="کرج", lat=35.83, lng=50.97)
    mashhad = variant(3, city="مشهد", lat=36.30, lng=59.60)
    results = rank(QUERY, mashhad, karaj)
    assert [result.id for result in results] == [karaj.id, mashhad.id]
    assert "کیلومتر دورتر · کرج" in results[0].labels[0]


def test_unknown_price_is_neutral_and_never_beats_an_exact_priced_match() -> None:
    negotiable = variant(2, price=None, deal_score=None)
    results = rank(QUERY, negotiable, EXACT_MATCH)
    assert results[0].id == EXACT_MATCH.id
    assert results[1].labels == (labels.PRICE_UNKNOWN,)
    assert results[1].is_exact is False


def test_vehicle_levels() -> None:
    model_query = RankingQuery(
        targets=(VehicleTarget(MentionLevel.MODEL, "پژو", "پژو 206"),)
    )
    other_trim = variant(2, trim=TRIM_5)
    other_model = variant(3, model="پژو پارس", trim="پژو پارس سال")
    results = rank(model_query, other_trim, other_model)
    # a same-brand, other-model listing scores 0.3: under the 0.4 cutoff
    assert [result.id for result in results] == [other_trim.id]
    assert results[0].match == 1.0  # any trim satisfies a model-level query
    brand_query = RankingQuery(targets=(VehicleTarget(MentionLevel.BRAND, "پژو"),))
    matches = {result.match for result in rank(brand_query, other_trim, other_model)}
    assert matches == {1.0}


def test_exact_match_precedes_a_near_miss_with_a_better_deal() -> None:
    poor_deal_exact = variant(2, deal_score=20)
    great_deal_near_miss = variant(3, year=1397, deal_score=99)
    results = rank(QUERY, great_deal_near_miss, poor_deal_exact)
    assert results[0].rank < results[1].rank  # raw rank alone would flip them
    assert [result.id for result in results] == [
        poor_deal_exact.id,
        great_deal_near_miss.id,
    ]


def test_other_model_never_outranks_the_requested_model() -> None:
    great_deal_405 = variant(2, model="پژو 405", trim="پژو 405 GLX", deal_score=99)
    plain_206 = variant(3, year=1396, price=990 * MILLION, deal_score=40)
    results = rank(QUERY, great_deal_405, plain_206)
    assert [result.id for result in results] == [plain_206.id, great_deal_405.id]
    assert results[0].rank < results[1].rank  # the 405 has the higher raw rank…
    assert results[1].labels[0] == "مدل متفاوت · پژو 405"  # …and says why it is last


def test_results_below_the_match_cutoff_are_dropped() -> None:
    wrong = variant(
        2,
        model="پژو پارس",
        trim="پژو پارس سال",
        year=1390,
        price=1_200 * MILLION,
        gearbox=Gearbox.AUTOMATIC,
    )
    assert rank(QUERY, wrong) == []


def test_browse_mode_ranks_by_deal_and_freshness() -> None:
    good_deal = variant(2, deal_score=95)
    stale = variant(3, deal_score=95, posted_at=NOW - timedelta(days=30))
    results = rank(RankingQuery(), EXACT_MATCH, stale, good_deal)
    # a fresh fair deal beats a month-old great one: freshness decays over 14 days
    assert [result.id for result in results] == [good_deal.id, EXACT_MATCH.id, stale.id]
    assert results[0].match is None and results[0].is_exact is True


def test_explicit_sort_orders_inside_the_exact_tier_first() -> None:
    cheap_near_miss = variant(2, year=1396, price=500 * MILLION)
    pricey_exact = variant(3, price=790 * MILLION)
    query = replace(QUERY, sort=SortKey.PRICE)
    results = rank(query, cheap_near_miss, pricey_exact, EXACT_MATCH)
    assert [result.id for result in results] == [
        EXACT_MATCH.id,
        pricey_exact.id,
        cheap_near_miss.id,
    ]


def test_ranking_is_deterministic_for_ties() -> None:
    twin = variant(2)
    assert rank(QUERY, twin, EXACT_MATCH) == rank(QUERY, EXACT_MATCH, twin)


def test_format_toman_switches_to_billions() -> None:
    assert labels.format_toman(20 * MILLION) == "۲۰ میلیون"
    assert labels.format_toman(1_250 * MILLION) == "۱.۲۵ میلیارد"
    assert labels.format_toman(2_000 * MILLION) == "۲ میلیارد"


def test_a_listing_under_the_km_floor_is_a_labelled_near_miss() -> None:
    query = replace(QUERY, km_min=50_000)
    inside, below = rank(query, EXACT_MATCH, variant(2, km=20_000))
    assert (inside.id, inside.is_exact) == (EXACT_MATCH.id, True)
    assert below.is_exact is False
    assert labels.under_km(30_000) in below.labels
