from pydantic import BaseModel

from enums import Category
from schemas.listing import ListingCard


class HistogramBucketRead(BaseModel):
    low: int
    high: int
    count: int


class TrimStatRead(BaseModel):
    trim: str
    count: int
    price_median: int | None


class ModelStats(BaseModel):
    model: str
    brand: str
    category: Category
    count: int
    year_min: int | None
    year_max: int | None
    price_median: int | None
    price_min: int | None
    price_max: int | None
    histogram: list[HistogramBucketRead]
    trims: list[TrimStatRead]
    top_deals: list[ListingCard]
