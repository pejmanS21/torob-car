"""Plain data carried between the search stages. No behaviour, no I/O."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from enums import Criterion, Fuel, Gearbox, MentionLevel, SortKey


@dataclass(frozen=True, slots=True)
class VehicleTarget:
    level: MentionLevel
    brand: str
    model: str | None = None
    trim: str | None = None


@dataclass(frozen=True, slots=True)
class ResolvedCity:
    name: str
    lat: float | None
    lng: float | None


@dataclass(frozen=True, slots=True)
class RankingQuery:
    targets: tuple[VehicleTarget, ...] = ()
    year_min: int | None = None
    year_max: int | None = None
    price_min: int | None = None
    price_max: int | None = None
    km_min: int | None = None
    km_max: int | None = None
    cities: tuple[ResolvedCity, ...] = ()
    gearbox: Gearbox | None = None
    fuel: Fuel | None = None
    colors: tuple[str, ...] = ()
    has_text: bool = False
    sort: SortKey = SortKey.RELEVANCE


@dataclass(frozen=True, slots=True)
class Candidate:
    id: uuid.UUID
    brand: str | None = None
    model: str | None = None
    trim: str | None = None
    year: int | None = None
    km: int | None = None
    price: int | None = None  # None when missing OR flagged price_suspect
    city: str | None = None
    lat: float | None = None
    lng: float | None = None
    gearbox: Gearbox | None = None
    fuel: Fuel | None = None
    color: str | None = None
    text_similarity: float | None = None
    deal_score: int | None = None
    posted_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class CriterionScore:
    criterion: Criterion
    closeness: float
    label: str | None = None


@dataclass(frozen=True, slots=True)
class RankedListing:
    id: uuid.UUID
    rank: float
    match: float | None
    is_exact: bool
    labels: tuple[str, ...]
