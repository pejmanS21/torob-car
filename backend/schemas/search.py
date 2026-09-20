from datetime import date
from typing import Self

from pydantic import BaseModel, Field, PositiveInt, ValidationError, model_validator

from core.text import MIN_JALALI_YEAR, jalali_year
from enums import (
    Category,
    DocumentStatus,
    Fuel,
    Gearbox,
    ParsedBy,
    PriceType,
    SortKey,
    Source,
)
from errors import invalid_search_error
from schemas.listing import ListingCard

MAX_QUERY_LENGTH = 300
MAX_PAGE_SIZE = 50
DEFAULT_PAGE_SIZE = 20


class VehicleMention(BaseModel):
    """A vehicle as the user wrote it — free text the resolver maps to the catalog."""

    brand: str | None = None
    model: str | None = None
    trim: str | None = None


class SearchIntent(BaseModel):
    """Everything a search can ask for. The LLM, the rules parser and the filter sheet
    all produce this one type, so there is exactly one ranking path."""

    category: Category | None = None
    vehicles: list[VehicleMention] = Field(default_factory=list)
    year_min: int | None = None
    year_max: int | None = None
    price_min: PositiveInt | None = Field(default=None, description="toman")
    price_max: PositiveInt | None = Field(default=None, description="toman")
    km_min: PositiveInt | None = None
    km_max: PositiveInt | None = None
    cities: list[str] = Field(default_factory=list)
    gearbox: Gearbox | None = None
    fuel: Fuel | None = None
    colors: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    # Most ads state neither, so a filter on these keeps the ads that never said
    # (see CandidateFilter): it narrows the answers, it does not hide the silent.
    price_types: list[PriceType] = Field(default_factory=list)
    document_statuses: list[DocumentStatus] = Field(default_factory=list)
    only_below_market: bool = False
    text: str | None = Field(default=None, description="anything not captured above")
    sort: SortKey = SortKey.RELEVANCE

    @model_validator(mode="after")
    def _check_ranges(self) -> Self:
        newest_year = jalali_year(date.today()) + 1
        for year in (self.year_min, self.year_max):
            if year is not None and not MIN_JALALI_YEAR <= year <= newest_year:
                raise ValueError(f"year must be a Jalali year up to {newest_year}")
        if self.year_min and self.year_max and self.year_min > self.year_max:
            raise ValueError("year_min must not exceed year_max")
        if self.price_min and self.price_max and self.price_min > self.price_max:
            raise ValueError("price_min must not exceed price_max")
        if self.km_min and self.km_max and self.km_min > self.km_max:
            raise ValueError("km_min must not exceed km_max")
        return self


class SearchOverrides(BaseModel):
    """Explicit filter-sheet parameters. Whatever is set here wins over what was
    parsed from the free-text query."""

    category: Category | None = None
    models: list[str] = Field(default_factory=list)
    cities: list[str] = Field(default_factory=list)
    year: int | None = None  # one exact year; year_min / year_max win over it
    year_min: int | None = None
    year_max: int | None = None
    price_min: PositiveInt | None = None
    price_max: PositiveInt | None = None
    km_min: PositiveInt | None = None
    km_max: PositiveInt | None = None
    gearbox: Gearbox | None = None
    sources: list[Source] = Field(default_factory=list)
    price_types: list[PriceType] = Field(default_factory=list)
    document_statuses: list[DocumentStatus] = Field(default_factory=list)
    only_below: bool | None = None
    sort: SortKey | None = None

    def apply_to(self, intent: SearchIntent) -> SearchIntent:
        changes: dict[str, object] = {
            "category": self.category,
            "cities": self.cities or None,
            "year_min": self.year_min or self.year,
            "year_max": self.year_max or self.year,
            "price_min": self.price_min,
            "price_max": self.price_max,
            "km_min": self.km_min,
            "km_max": self.km_max,
            "gearbox": self.gearbox,
            "sources": self.sources or None,
            "price_types": self.price_types or None,
            "document_statuses": self.document_statuses or None,
            "only_below_market": self.only_below,
            "sort": self.sort,
        }
        if self.models:
            changes["vehicles"] = [VehicleMention(model=name) for name in self.models]
        stated = {name: value for name, value in changes.items() if value is not None}
        try:
            return SearchIntent.model_validate({**intent.model_dump(), **stated})
        except ValidationError as error:
            raise invalid_search_error("Invalid search filters", error) from error


class SearchParams(SearchOverrides):
    """Every query parameter of GET /search as ONE model. FastAPI cannot mix a
    query-parameter model with individual `Query()` parameters."""

    q: str | None = Field(default=None, max_length=MAX_QUERY_LENGTH)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)


class IntentRead(SearchIntent):
    chips: list[str]


class SearchResponse(BaseModel):
    intent: IntentRead
    parsed_by: ParsedBy
    total: int
    exact_count: int
    page: int
    page_size: int
    items: list[ListingCard]
