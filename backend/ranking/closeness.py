"""One pure function per criterion: (query, candidate, weights) → CriterionScore, or
None when the user did not state that criterion. Closeness is 1.0 for a full match,
decays to 0.0, and is `unknown_closeness` when the listing lacks the value."""

import math
from collections.abc import Callable

from enums import Criterion, MentionLevel
from ranking import labels
from ranking.types import Candidate, CriterionScore, RankingQuery, VehicleTarget
from ranking.weights import RankingWeights

EARTH_RADIUS_KM = 6371.0
EXACT = 1.0
MISS = 0.0

type ClosenessFunction = Callable[
    [RankingQuery, Candidate, RankingWeights], CriterionScore | None
]


def haversine_km(lat_a: float, lng_a: float, lat_b: float, lng_b: float) -> float:
    lat_delta = math.radians(lat_b - lat_a)
    lng_delta = math.radians(lng_b - lng_a)
    chord = (
        math.sin(lat_delta / 2) ** 2
        + math.cos(math.radians(lat_a))
        * math.cos(math.radians(lat_b))
        * math.sin(lng_delta / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(chord))


def _linear_decay(excess: float, tolerance: float) -> float:
    if tolerance <= 0:
        return MISS
    return max(MISS, EXACT - excess / tolerance)


def _target_closeness(
    target: VehicleTarget, candidate: Candidate, weights: RankingWeights
) -> float:
    if candidate.brand != target.brand:
        return MISS
    if target.level is MentionLevel.BRAND:
        return EXACT
    if candidate.model != target.model:
        return weights.same_brand_other_model
    if target.level is MentionLevel.MODEL or candidate.trim == target.trim:
        return EXACT
    return weights.same_model_other_trim


def vehicle_closeness(
    query: RankingQuery, candidate: Candidate, weights: RankingWeights
) -> CriterionScore | None:
    if not query.targets:
        return None
    closeness = max(
        _target_closeness(target, candidate, weights) for target in query.targets
    )
    label = None
    if closeness == weights.same_model_other_trim and candidate.trim:
        label = labels.other_trim(candidate.trim)
    elif closeness < weights.same_model_other_trim and candidate.model:
        label = labels.other_model(candidate.model)
    return CriterionScore(Criterion.VEHICLE, closeness, label)


def price_closeness(
    query: RankingQuery, candidate: Candidate, weights: RankingWeights
) -> CriterionScore | None:
    if query.price_min is None and query.price_max is None:
        return None
    if candidate.price is None:
        return CriterionScore(
            Criterion.PRICE, weights.unknown_closeness, labels.PRICE_UNKNOWN
        )
    if query.price_max is not None and candidate.price > query.price_max:
        excess = candidate.price - query.price_max
        closeness = _linear_decay(excess, query.price_max * weights.price_tolerance)
        return CriterionScore(Criterion.PRICE, closeness, labels.over_budget(excess))
    if query.price_min is not None and candidate.price < query.price_min:
        shortfall = query.price_min - candidate.price
        closeness = _linear_decay(shortfall, query.price_min * weights.price_tolerance)
        return CriterionScore(
            Criterion.PRICE, closeness, labels.under_budget(shortfall)
        )
    return CriterionScore(Criterion.PRICE, EXACT)


def year_closeness(
    query: RankingQuery, candidate: Candidate, weights: RankingWeights
) -> CriterionScore | None:
    if query.year_min is None and query.year_max is None:
        return None
    if candidate.year is None:
        return CriterionScore(Criterion.YEAR, weights.unknown_closeness)
    if query.year_min is not None and candidate.year < query.year_min:
        gap = query.year_min - candidate.year
        return CriterionScore(
            Criterion.YEAR,
            _linear_decay(gap, weights.year_tolerance),
            labels.year_gap(gap, older=True),
        )
    if query.year_max is not None and candidate.year > query.year_max:
        gap = candidate.year - query.year_max
        return CriterionScore(
            Criterion.YEAR,
            _linear_decay(gap, weights.year_tolerance),
            labels.year_gap(gap, older=False),
        )
    return CriterionScore(Criterion.YEAR, EXACT)


def km_closeness(
    query: RankingQuery, candidate: Candidate, weights: RankingWeights
) -> CriterionScore | None:
    if query.km_max is None:
        return None
    if candidate.km is None:
        return CriterionScore(
            Criterion.KM, weights.unknown_closeness, labels.KM_UNKNOWN
        )
    if candidate.km <= query.km_max:
        return CriterionScore(Criterion.KM, EXACT)
    excess = candidate.km - query.km_max
    closeness = _linear_decay(excess, query.km_max * weights.km_tolerance)
    return CriterionScore(Criterion.KM, closeness, labels.over_km(excess))


def city_closeness(
    query: RankingQuery, candidate: Candidate, weights: RankingWeights
) -> CriterionScore | None:
    if not query.cities:
        return None
    if any(city.name == candidate.city for city in query.cities):
        return CriterionScore(Criterion.CITY, EXACT)
    if candidate.lat is None or candidate.lng is None:
        return CriterionScore(
            Criterion.CITY, MISS, labels.other_city(candidate.city or "")
        )
    distances = [
        haversine_km(city.lat, city.lng, candidate.lat, candidate.lng)
        for city in query.cities
        if city.lat is not None and city.lng is not None
    ]
    if not distances:
        return CriterionScore(
            Criterion.CITY, MISS, labels.other_city(candidate.city or "")
        )
    nearest = min(distances)
    closeness = min(
        weights.other_city_ceiling, _linear_decay(nearest, weights.city_radius_km)
    )
    return CriterionScore(
        Criterion.CITY, closeness, labels.farther(nearest, candidate.city or "")
    )


def gearbox_closeness(
    query: RankingQuery, candidate: Candidate, weights: RankingWeights
) -> CriterionScore | None:
    if query.gearbox is None:
        return None
    if candidate.gearbox is None:
        return CriterionScore(Criterion.GEARBOX, weights.unknown_closeness)
    if candidate.gearbox is query.gearbox:
        return CriterionScore(Criterion.GEARBOX, EXACT)
    return CriterionScore(Criterion.GEARBOX, MISS, labels.gearbox_is(candidate.gearbox))


def fuel_closeness(
    query: RankingQuery, candidate: Candidate, weights: RankingWeights
) -> CriterionScore | None:
    if query.fuel is None:
        return None
    if candidate.fuel is None:
        return CriterionScore(Criterion.FUEL, weights.unknown_closeness)
    if candidate.fuel is query.fuel:
        return CriterionScore(Criterion.FUEL, EXACT)
    return CriterionScore(Criterion.FUEL, MISS, labels.fuel_is(candidate.fuel))


def color_closeness(
    query: RankingQuery, candidate: Candidate, weights: RankingWeights
) -> CriterionScore | None:
    if not query.colors:
        return None
    if candidate.color is None:
        return CriterionScore(Criterion.COLOR, weights.unknown_closeness)
    if candidate.color in query.colors:
        return CriterionScore(Criterion.COLOR, EXACT)
    return CriterionScore(Criterion.COLOR, MISS, labels.color_is(candidate.color))


def text_closeness(
    query: RankingQuery, candidate: Candidate, weights: RankingWeights
) -> CriterionScore | None:
    if not query.has_text:
        return None
    return CriterionScore(Criterion.TEXT, candidate.text_similarity or MISS)


CLOSENESS_FUNCTIONS: tuple[ClosenessFunction, ...] = (
    vehicle_closeness,
    price_closeness,
    year_closeness,
    city_closeness,
    km_closeness,
    gearbox_closeness,
    fuel_closeness,
    text_closeness,
    color_closeness,
)
