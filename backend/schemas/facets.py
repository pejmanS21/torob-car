from datetime import datetime

from pydantic import BaseModel

from enums import Category, DocumentStatus, Gearbox, PriceType, Source


class FacetCount(BaseModel):
    value: str
    count: int


class ModelFacet(BaseModel):
    brand: str
    model: str
    count: int


class FacetRanges(BaseModel):
    """What the current search can still reach, for the range inputs' hints."""

    price_min: int | None
    price_max: int | None
    km_min: int | None
    km_max: int | None
    year_min: int | None
    year_max: int | None


class AppliedFilters(BaseModel):
    """Every filter in force — typed into the query or ticked in the panel — in the
    panel's own vocabulary (catalog model names, city names), so it can show them."""

    category: Category | None
    models: list[str]
    cities: list[str]
    gearbox: Gearbox | None
    sources: list[Source]
    price_types: list[PriceType]
    document_statuses: list[DocumentStatus]
    price_min: int | None
    price_max: int | None
    km_min: int | None
    km_max: int | None
    year_min: int | None
    year_max: int | None
    only_below_market: bool


class Facets(BaseModel):
    categories: dict[Category, int]
    models: list[ModelFacet]
    cities: list[FacetCount]
    sources: list[FacetCount]
    gearboxes: list[FacetCount]
    ranges: FacetRanges
    applied: AppliedFilters
    model_count: int
    data_as_of: datetime | None
