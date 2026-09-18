"""ListingRanker — the sorting algorithm (spec §7.4). Pure Python, no I/O.

match = Σ wᵢ·cᵢ / Σ wᵢ      over the criteria the user stated
rank  = 0.55·match + 0.30·deal + 0.15·fresh

`rank` orders listings INSIDE a tier; two tiers come first, whatever the rank:
1. exact matches (every stated criterion satisfied) precede near-misses;
2. the vehicle is identity, the other criteria are preferences — listings of the
   requested model precede listings that only share its brand. Without this a
   great-deal Peugeot 405 outranks real 206s for a "206" search.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from enums import Criterion, SortKey
from ranking.closeness import CLOSENESS_FUNCTIONS, EXACT
from ranking.types import Candidate, CriterionScore, RankedListing, RankingQuery
from ranking.weights import DEFAULT_WEIGHTS, RankingWeights

SECONDS_PER_DAY = 86_400
MAX_DEAL_SCORE = 100
RANK_PRECISION = 4
_MISSING_LAST = math.inf
_NO_DEAL_SCORE = -1


@dataclass(frozen=True, slots=True)
class _Scored:
    listing: RankedListing
    candidate: Candidate
    off_model: bool


class ListingRanker:
    def __init__(self, weights: RankingWeights = DEFAULT_WEIGHTS) -> None:
        self._weights = weights

    def rank(
        self, query: RankingQuery, candidates: Sequence[Candidate], now: datetime
    ) -> list[RankedListing]:
        scored = [self._score(query, candidate, now) for candidate in candidates]
        kept = [item for item in scored if self._passes_cutoff(item.listing)]
        kept.sort(key=lambda item: self._sort_key(query.sort, item))
        return [item.listing for item in kept]

    def _score(
        self, query: RankingQuery, candidate: Candidate, now: datetime
    ) -> _Scored:
        scores = [
            score
            for function in CLOSENESS_FUNCTIONS
            if (score := function(query, candidate, self._weights))
        ]
        match = self._match(scores)
        rank = self._combine(
            match, self._deal(candidate), self._freshness(candidate, now)
        )
        listing = RankedListing(
            id=candidate.id,
            rank=round(rank, RANK_PRECISION),
            match=None if match is None else round(match, RANK_PRECISION),
            is_exact=all(score.closeness == EXACT for score in scores),
            labels=self._labels(scores),
        )
        return _Scored(listing, candidate, self._is_off_model(scores))

    def _is_off_model(self, scores: Sequence[CriterionScore]) -> bool:
        return any(
            score.criterion is Criterion.VEHICLE
            and score.closeness < self._weights.same_model_other_trim
            for score in scores
        )

    def _match(self, scores: Sequence[CriterionScore]) -> float | None:
        if not scores:
            return None
        total_weight = sum(self._weights.criteria[score.criterion] for score in scores)
        weighted = sum(
            self._weights.criteria[score.criterion] * score.closeness
            for score in scores
        )
        return weighted / total_weight

    def _combine(self, match: float | None, deal: float, fresh: float) -> float:
        weights = self._weights
        if match is None:
            return weights.browse_deal_share * deal + weights.browse_fresh_share * fresh
        return (
            weights.match_share * match
            + weights.deal_share * deal
            + weights.fresh_share * fresh
        )

    def _deal(self, candidate: Candidate) -> float:
        if candidate.deal_score is None:
            return self._weights.neutral_deal
        return candidate.deal_score / MAX_DEAL_SCORE

    def _freshness(self, candidate: Candidate, now: datetime) -> float:
        if candidate.posted_at is None:
            return self._weights.neutral_fresh
        age_seconds = (now - candidate.posted_at).total_seconds()
        age_days = max(0.0, age_seconds / SECONDS_PER_DAY)
        return math.exp(-age_days / self._weights.freshness_decay_days)

    def _weighted_loss(self, score: CriterionScore) -> float:
        return self._weights.criteria[score.criterion] * (EXACT - score.closeness)

    def _labels(self, scores: Sequence[CriterionScore]) -> tuple[str, ...]:
        missed = [score for score in scores if score.closeness < EXACT]
        missed.sort(key=self._weighted_loss, reverse=True)
        found = [score.label for score in missed if score.label]
        return tuple(found[: self._weights.max_labels])

    def _passes_cutoff(self, listing: RankedListing) -> bool:
        return listing.match is None or listing.match >= self._weights.min_match_score

    @staticmethod
    def _explicit_value(sort: SortKey, candidate: Candidate, posted: float) -> float:
        if sort is SortKey.PRICE:
            return candidate.price if candidate.price is not None else _MISSING_LAST
        if sort is SortKey.KM:
            return candidate.km if candidate.km is not None else _MISSING_LAST
        if sort is SortKey.NEWEST:
            return -posted
        deal_score = candidate.deal_score
        return -(deal_score if deal_score is not None else _NO_DEAL_SCORE)

    @classmethod
    def _sort_key(cls, sort: SortKey, item: _Scored) -> tuple[object, ...]:
        listing, candidate = item.listing, item.candidate
        posted = candidate.posted_at.timestamp() if candidate.posted_at else 0.0
        tier = (not listing.is_exact, item.off_model)
        relevance = (-listing.rank, -posted, str(listing.id))
        if sort is SortKey.RELEVANCE:
            return (*tier, *relevance)
        explicit = cls._explicit_value(sort, candidate, posted)
        return (*tier, explicit, *relevance)
