from datetime import date
from typing import Self

from pydantic import BaseModel, Field, PositiveInt, model_validator

from core.text import jalali_year
from enums import Category, Fuel, Gearbox, ParsedBy, SortKey
from schemas.listing import ListingCard

MIN_SEARCH_YEAR = 1340
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
    km_max: PositiveInt | None = None
    cities: list[str] = Field(default_factory=list)
    gearbox: Gearbox | None = None
    fuel: Fuel | None = None
    colors: list[str] = Field(default_factory=list)
    only_below_market: bool = False
    text: str | None = Field(default=None, description="anything not captured above")
    sort: SortKey = SortKey.RELEVANCE

    @model_validator(mode="after")
    def _check_ranges(self) -> Self:
        newest_year = jalali_year(date.today()) + 1
        for year in (self.year_min, self.year_max):
            if year is not None and not MIN_SEARCH_YEAR <= year <= newest_year:
                raise ValueError(f"year must be a Jalali year up to {newest_year}")
        if self.year_min and self.year_max and self.year_min > self.year_max:
            raise ValueError("year_min must not exceed year_max")
        if self.price_min and self.price_max and self.price_min > self.price_max:
            raise ValueError("price_min must not exceed price_max")
        return self


class SearchOverrides(BaseModel):
    """Explicit filter-sheet parameters. Whatever is set here wins over what was
    parsed from the free-text query."""

    category: Category | None = None
    models: list[str] = Field(default_factory=list)
    cities: list[str] = Field(default_factory=list)
    year: int | None = None
    price_max: PositiveInt | None = None
    km_max: PositiveInt | None = None
    gearbox: Gearbox | None = None
    only_below: bool | None = None
    sort: SortKey | None = None

    def apply_to(self, intent: SearchIntent) -> SearchIntent:
        changes: dict[str, object] = {
            "category": self.category,
            "cities": self.cities or None,
            "year_min": self.year,
            "year_max": self.year,
            "price_max": self.price_max,
            "km_max": self.km_max,
            "gearbox": self.gearbox,
            "only_below_market": self.only_below,
            "sort": self.sort,
        }
        if self.models:
            changes["vehicles"] = [VehicleMention(model=name) for name in self.models]
        stated = {name: value for name, value in changes.items() if value is not None}
        return SearchIntent.model_validate({**intent.model_dump(), **stated})


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
