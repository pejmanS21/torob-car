"""Field parsers for raw Divar CSV values. Pure functions, no I/O."""

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from core.text import MIN_JALALI_YEAR, normalize_persian, to_ascii_digits

MIN_PLAUSIBLE_PRICE_TOMAN = 10_000_000
MAX_PLAUSIBLE_KM = 1_000_000
MAX_JALALI_YEAR = 1420
GREGORIAN_TO_JALALI_OFFSET = 621
MAX_INSURANCE_MONTHS = 12
URL_SEPARATOR = "|"
LOCATION_MARKER = " در "
LOCATION_SEPARATOR = "،"
BEFORE_YEAR_MARKER = "قبل از"

_FIXED_AGE_HOURS = {"نیم ساعت پیش": 0.5, "دیروز": 24.0, "پریروز": 48.0}
_UNIT_HOURS = {"ساعت": 1, "روز": 24, "هفته": 168, "ماه": 720, "سال": 8760}
_RELATIVE_AGE = re.compile(r"(?:(\d+) )?(ساعت|روز|هفته|ماه|سال) پیش")
_FOUR_DIGITS = re.compile(r"\d{4}")

# Brands written with spaces in Divar's «برند و مدل» strings (normalised form).
MULTI_TOKEN_BRANDS: tuple[str, ...] = (
    "اس وای ام", "ایران دوچرخ", "ایران خودرو", "کی تی ام", "کی ام سی", "کی وی",
    "جی ای سی", "جی پی ایکس", "جی سی موتور", "ام وی ام", "ام تک", "بی ای سی",
    "بی وای دی", "بی اس آ", "بی ام و", "ان اس یو", "ان ام بی", "تی وی اس", "به پر",
    "تک تاز", "گس گس", "سی اف موتو", "3 چرخ", "4 چرخ",
)  # fmt: skip


@dataclass(frozen=True, slots=True)
class BrandModel:
    brand: str
    model: str


def parse_digits(raw: str) -> int | None:
    digits = re.sub(r"\D", "", to_ascii_digits(raw))
    return int(digits) if digits else None


def parse_price(raw: str) -> int | None:
    price = parse_digits(raw)
    if price is None or price < MIN_PLAUSIBLE_PRICE_TOMAN:
        return None
    return price


def parse_km(raw: str) -> int | None:
    km = parse_digits(raw)
    if km is None or km >= MAX_PLAUSIBLE_KM:
        return None
    return km


def parse_year(raw: str) -> int | None:
    text = to_ascii_digits(raw).replace(",", "")
    found = _FOUR_DIGITS.search(text)
    if found is None:
        return None
    year = int(found.group())
    if year > MAX_JALALI_YEAR:
        year -= GREGORIAN_TO_JALALI_OFFSET
    if BEFORE_YEAR_MARKER in text:
        year -= 1
    return year if MIN_JALALI_YEAR <= year <= MAX_JALALI_YEAR else None


def parse_insurance_months(raw: str) -> int | None:
    months = parse_digits(raw)
    if months is None or months > MAX_INSURANCE_MONTHS:
        return None
    return months


def parse_posted_at(posted_raw: str, fetched_at: datetime) -> datetime | None:
    phrase = normalize_persian(posted_raw.split(LOCATION_MARKER, 1)[0])
    hours = _FIXED_AGE_HOURS.get(phrase)
    if hours is None:
        matched = _RELATIVE_AGE.fullmatch(phrase)
        if matched is None:
            return None
        hours = float(int(matched.group(1) or 1) * _UNIT_HOURS[matched.group(2)])
    return fetched_at - timedelta(hours=hours)


def parse_district(posted_raw: str) -> str | None:
    _, marker, location = posted_raw.partition(LOCATION_MARKER)
    parts = [part.strip() for part in location.split(LOCATION_SEPARATOR)]
    return parts[1] if marker and len(parts) > 1 and parts[1] else None


def parse_fetched_at(raw: str) -> datetime:
    return datetime.fromtimestamp(int(raw), tz=UTC)


def parse_coordinate(raw: str) -> float | None:
    return float(raw) if raw.strip() else None


def split_urls(raw: str) -> list[str]:
    return [url.strip() for url in raw.split(URL_SEPARATOR) if url.strip()]


def split_brand_model(trim: str) -> BrandModel:
    """`پژو 206 تیپ ۲` → brand `پژو`, model `پژو 206` (both normalised).
    ponytail: token heuristic; irregular families mis-group. Upgrade path is the
    one-time LLM normalisation of the ~1,262 catalog strings in Spec 2."""
    normalized = normalize_persian(trim)
    for brand in MULTI_TOKEN_BRANDS:
        if normalized == brand or normalized.startswith(brand + " "):
            rest = normalized[len(brand) :].split()
            return BrandModel(brand, f"{brand} {rest[0]}" if rest else brand)
    first, *others = trim.split(" ")
    brand = normalize_persian(first)
    second = normalize_persian(others[0]) if others else ""
    return BrandModel(brand, f"{brand} {second}" if second else brand)
