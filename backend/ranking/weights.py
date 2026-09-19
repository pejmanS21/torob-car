"""Every tunable number of the ranking algorithm, in one frozen place (spec §7.4).
Changing a value here means re-running the golden-query suite."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from enums import Criterion

# Verdict thresholds (percent vs the estimate). The single source for both the
# "only below market" filter and the cheap/fair/expensive verdict.
CHEAP_DIFF_PCT = -5.0
EXPENSIVE_DIFF_PCT = 6.0


def _default_criterion_weights() -> Mapping[Criterion, float]:
    return MappingProxyType(
        {
            Criterion.VEHICLE: 3.0,
            Criterion.PRICE: 2.5,
            Criterion.YEAR: 2.0,
            Criterion.CITY: 1.5,
            Criterion.KM: 1.5,
            Criterion.GEARBOX: 1.0,
            Criterion.FUEL: 1.0,
            Criterion.TEXT: 1.0,
            Criterion.COLOR: 0.5,
        }
    )


@dataclass(frozen=True, slots=True)
class RankingWeights:
    criteria: Mapping[Criterion, float] = field(
        default_factory=_default_criterion_weights
    )
    match_share: float = 0.55
    deal_share: float = 0.30
    fresh_share: float = 0.15
    browse_deal_share: float = 0.67
    browse_fresh_share: float = 0.33
    min_match_score: float = 0.4
    unknown_closeness: float = 0.5
    neutral_deal: float = 0.5
    neutral_fresh: float = 0.5
    same_model_other_trim: float = 0.8
    same_brand_other_model: float = 0.3
    price_tolerance: float = 0.25
    km_tolerance: float = 0.5
    year_tolerance: int = 5
    city_radius_km: float = 300.0
    other_city_ceiling: float = 0.9
    freshness_decay_days: float = 14.0
    max_labels: int = 2


DEFAULT_WEIGHTS = RankingWeights()
