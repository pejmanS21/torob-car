import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from enums import (
    BodyCondition,
    Category,
    DocumentStatus,
    EstimateBasis,
    Fuel,
    Gearbox,
    PriceType,
    Source,
    Verdict,
)


class ListingCard(BaseModel):
    id: uuid.UUID
    token: str
    title: str
    source: Source
    category: Category
    brand: str | None
    model: str | None
    trim: str | None
    year: int | None
    km: int | None
    price: int | None
    city: str
    district: str | None
    lat: float | None
    lng: float | None
    gearbox: Gearbox | None
    fuel: Fuel | None
    body_condition: BodyCondition | None
    insurance_months: int | None
    thumbnail_url: str | None
    posted_at: datetime | None
    est_price: int | None
    diff_pct: float | None
    deal_score: int | None
    verdict: Verdict
    match_score: float | None = None
    is_exact: bool = True
    near_miss_labels: list[str] = []


class PriceBreakdown(BaseModel):
    base: int | None
    km_adjustment: int | None
    insurance_adjustment: int | None
    est_basis: EstimateBasis
    est_sample_size: int


class ListingDetail(ListingCard):
    url: str
    description: str
    image_urls: list[str]
    color: str | None
    is_dealer: bool
    price_type: PriceType | None
    document_status: DocumentStatus | None
    attributes: dict[str, Any]
    price_breakdown: PriceBreakdown
