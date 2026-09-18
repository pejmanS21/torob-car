import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from enums import Category, EstimateBasis, Fuel, Gearbox, Verdict


class ListingCard(BaseModel):
    id: uuid.UUID
    token: str
    title: str
    category: Category
    brand: str | None
    model: str | None
    trim: str | None
    year: int | None
    km: int | None
    price: int | None
    city: str
    district: str | None
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
    lat: float | None
    lng: float | None
    gearbox: Gearbox | None
    fuel: Fuel | None
    color: str | None
    insurance_months: int | None
    is_dealer: bool
    attributes: dict[str, Any]
    price_breakdown: PriceBreakdown
