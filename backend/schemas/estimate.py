from datetime import date
from typing import Self

from pydantic import BaseModel, Field, PositiveInt, model_validator

from core.text import MIN_JALALI_YEAR, jalali_year
from enums import BodyCondition, Category, EstimateBasis, Verdict
from schemas.listing import ListingCard

MAX_TRIM_LENGTH = 255
MAX_KM = 2_000_000
MAX_INSURANCE_MONTHS = 24
SIMILAR_YEAR_SPAN = 1  # /estimates "similar" = trim, year ± 1, category


class EstimateRequest(BaseModel):
    category: Category
    trim: str = Field(min_length=1, max_length=MAX_TRIM_LENGTH)
    year: int
    km: int | None = Field(default=None, ge=0, le=MAX_KM)
    insurance_months: int | None = Field(default=None, ge=0, le=MAX_INSURANCE_MONTHS)
    body_condition: BodyCondition | None = None
    asking_price: PositiveInt | None = Field(default=None, description="toman")

    @model_validator(mode="after")
    def _check_year(self) -> Self:
        # ± SIMILAR_YEAR_SPAN must stay inside SearchIntent's own year bounds.
        newest = jalali_year(date.today())
        oldest = MIN_JALALI_YEAR + SIMILAR_YEAR_SPAN
        if not oldest <= self.year <= newest:
            raise ValueError(
                f"year must be a Jalali year between {oldest} and {newest}"
            )
        return self


class EstimateBreakdown(BaseModel):
    base: int
    km_adjustment: int
    insurance_adjustment: int


class EstimateResponse(BaseModel):
    est_price: int
    low: int
    high: int
    est_basis: EstimateBasis
    est_sample_size: int
    breakdown: EstimateBreakdown
    asking_verdict: Verdict | None
    asking_diff_pct: float | None
    similar: list[ListingCard]
