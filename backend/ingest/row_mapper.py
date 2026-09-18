"""One raw CSV row → one validated NormalizedListing. The CSV is a trust boundary."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from core.text import normalize_persian
from enums import BodyCondition, Category, Fuel, Gearbox
from ingest import column_maps as columns
from ingest import normalizers

NULLED_PRICE = "price_placeholder"
NULLED_KM = "km_implausible"
NULLED_YEAR = "year_unparsed"
NULLED_POSTED_AT = "posted_at_unparsed"


class RowRejectedError(Exception):
    """The row cannot become a listing. Collected in the ingest report, not fatal."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class NormalizedListing(BaseModel):
    token: str = Field(min_length=1)
    url: str
    category: Category
    trim: str | None
    brand: str | None
    model: str | None
    city: str = Field(min_length=1)
    district: str | None
    title: str = Field(min_length=1)
    title_normalized: str
    description: str
    year: int | None
    km: int | None
    price: int | None
    gearbox: Gearbox | None
    fuel: Fuel | None
    color: str | None
    body_condition: BodyCondition | None
    insurance_months: int | None
    vehicle_type: str | None
    is_dealer: bool
    lat: float | None
    lng: float | None
    posted_at: datetime | None
    fetched_at: datetime
    image_urls: list[str]
    thumbnail_urls: list[str]
    attributes: dict[str, Any]


@dataclass(frozen=True, slots=True)
class MappedRow:
    listing: NormalizedListing
    nulled: tuple[str, ...]


def _text(row: Mapping[str, str], column: str) -> str:
    return (row.get(column) or "").strip()


def _optional(row: Mapping[str, str], column: str) -> str | None:
    return _text(row, column) or None


def _require(row: Mapping[str, str], column: str) -> str:
    value = _text(row, column)
    if not value:
        raise RowRejectedError(f"missing_{column}")
    return value


def _gearbox(row: Mapping[str, str]) -> Gearbox | None:
    for column in columns.GEARBOX_COLUMNS:
        gearbox = columns.lookup_value(
            _text(row, column), columns.GEARBOX_VALUES, column
        )
        if gearbox is not None:
            return gearbox
    return None


def _attributes(row: Mapping[str, str], category: Category) -> dict[str, Any]:
    names = list(columns.ATTRIBUTE_COLUMNS)
    if category is Category.RENTAL:
        names.append(columns.RENT_PRICE_COLUMN)
    return {name: _text(row, name) for name in names if _text(row, name)}


def _nulled(
    row: Mapping[str, str],
    listing: NormalizedListing,
    price_column: str | None,
    year_column: str,
) -> tuple[str, ...]:
    checks = (
        (
            NULLED_PRICE,
            price_column is not None and _text(row, price_column),
            listing.price,
        ),
        (NULLED_KM, _text(row, columns.KM_COLUMN), listing.km),
        (NULLED_YEAR, _text(row, year_column), listing.year),
        (NULLED_POSTED_AT, _text(row, "posted_raw"), listing.posted_at),
    )
    return tuple(name for name, raw, parsed in checks if raw and parsed is None)


def map_row(row: Mapping[str, str]) -> MappedRow:
    category = columns.detect_category(row)
    if category is None:
        raise RowRejectedError("unknown_category")
    column_map = columns.COLUMN_MAPS[category]
    trim = _optional(row, columns.TRIM_COLUMN)
    brand_model = normalizers.split_brand_model(trim) if trim else None
    fetched_at = normalizers.parse_fetched_at(_require(row, "fetched_at"))
    posted_raw = _text(row, "posted_raw")
    title = _require(row, "title")
    listing = NormalizedListing(
        token=_require(row, "token"),
        url=_text(row, "url"),
        category=category,
        trim=trim,
        brand=brand_model.brand if brand_model else None,
        model=brand_model.model if brand_model else None,
        city=_require(row, "city"),
        district=normalizers.parse_district(posted_raw),
        title=title,
        title_normalized=normalize_persian(title),
        description=_text(row, "description"),
        year=normalizers.parse_year(_text(row, column_map.year)),
        km=normalizers.parse_km(_text(row, columns.KM_COLUMN)),
        price=(
            normalizers.parse_price(_text(row, column_map.price))
            if column_map.price
            else None
        ),
        gearbox=_gearbox(row),
        fuel=columns.lookup_value(
            _text(row, columns.FUEL_COLUMN), columns.FUEL_VALUES, columns.FUEL_COLUMN
        ),
        color=_optional(row, columns.COLOR_COLUMN),
        body_condition=columns.lookup_value(
            _text(row, columns.BODY_COLUMN), columns.BODY_VALUES, columns.BODY_COLUMN
        ),
        insurance_months=normalizers.parse_insurance_months(
            _text(row, columns.INSURANCE_COLUMN)
        ),
        vehicle_type=_optional(row, columns.VEHICLE_TYPE_COLUMN),
        is_dealer=_text(row, columns.BUSINESS_TYPE_COLUMN)
        != columns.PERSONAL_BUSINESS_TYPE,
        lat=normalizers.parse_coordinate(_text(row, "latitude")),
        lng=normalizers.parse_coordinate(_text(row, "longitude")),
        posted_at=normalizers.parse_posted_at(posted_raw, fetched_at),
        fetched_at=fetched_at,
        image_urls=normalizers.split_urls(_text(row, "image_urls")),
        thumbnail_urls=normalizers.split_urls(_text(row, "thumbnail_urls")),
        attributes=_attributes(row, category),
    )
    return MappedRow(listing, _nulled(row, listing, column_map.price, column_map.year))
