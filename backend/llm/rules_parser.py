"""Deterministic fallback parser, used whenever the LLM is unavailable (spec §8.3).
A Python port of frontend/src/lib/search.ts `parseQuery`, generalised: whatever it
cannot classify becomes one VehicleMention for the catalog resolver to try."""

import re
from collections.abc import Collection

from core.text import normalize_persian
from enums import Gearbox
from schemas.search import SearchIntent, VehicleMention

TOMAN_PER_MILLION = 1_000_000
TOMAN_PER_BILLION = 1_000_000_000
IMPLICIT_BILLION_BELOW = 5  # «زیر 1.2» means billions
KM_PER_THOUSAND = 1_000
LOW_MILEAGE_KM = 90_000
CENTURY_PIVOT = 50  # «مدل 98» → 1398, «مدل 02» → 1402
BILLION_WORD = "میلیارد"
MILEAGE_WORDS = ("کیلومتر", "کارکرد")

_LIMIT = r"(?:زیر|کمتر از|تا|حداکثر|سقف)"
_PRICE = re.compile(
    rf"{_LIMIT}\s*(\d+(?:[./]\d+)?)\s*(هزار)?\s*(میلیارد|میلیون|تومان|تومن|کیلومتر|کارکرد)?"
)
_ONE_BILLION = re.compile(r"(?:زیر|تا)?\s*یک میلیارد")
_KM = re.compile(rf"(?:کارکرد\s*)?{_LIMIT}\s*(\d+)\s*(?:هزار)?\s*(?:کیلومتر|کارکرد)")
_LOW_MILEAGE = re.compile(r"کم\s?کارکرد|کم کار")
_YEAR = re.compile(r"(?:مدل|سال)\s*(1[34]\d\d|\d\d)\b(\s*به بالا)?")
_AUTOMATIC = re.compile(r"\bات(?:و)?مات(?:یک)?\b")
_MANUAL = re.compile(r"دنده\s?ای|دنده")
_BELOW_MARKET = re.compile(r"ارزان\w*|زیر قیمت|به صرفه")
_STOP_WORDS = frozenset(
    {"میخوام", "می", "خوام", "یه", "یک", "ماشین", "خودرو", "در", "تو", "توی"}
    | {"با", "و", "اطراف", "رنگ", "دنبال", "هستم"}
)


class _Text:
    """The query with every recognised clause blanked out as it is consumed."""

    def __init__(self, text: str) -> None:
        self.remaining = text

    def take(self, pattern: re.Pattern[str]) -> re.Match[str] | None:
        found = pattern.search(self.remaining)
        if found:
            start, end = found.span()
            self.remaining = f"{self.remaining[:start]} {self.remaining[end:]}"
        return found


def _is_mileage(thousand: str | None, unit: str | None) -> bool:
    return unit in MILEAGE_WORDS or (bool(thousand) and unit is None)


def _price_max(text: _Text) -> int | None:
    for found in _PRICE.finditer(text.remaining):
        value, thousand, unit = found.groups()
        if _is_mileage(thousand, unit):
            continue
        text.remaining = text.remaining.replace(found.group(), " ", 1)
        amount = float(value.replace("/", "."))
        in_billions = unit == BILLION_WORD or (
            unit is None and amount < IMPLICIT_BILLION_BELOW
        )
        return round(amount * (TOMAN_PER_BILLION if in_billions else TOMAN_PER_MILLION))
    return TOMAN_PER_BILLION if text.take(_ONE_BILLION) else None


def _km_max(text: _Text) -> int | None:
    found = text.take(_KM)
    if found:
        value = int(found.group(1))
        return value * KM_PER_THOUSAND if value < KM_PER_THOUSAND else value
    return LOW_MILEAGE_KM if text.take(_LOW_MILEAGE) else None


def _years(text: _Text) -> tuple[int | None, int | None]:
    found = text.take(_YEAR)
    if not found:
        return None, None
    year = int(found.group(1))
    if year < 100:
        year += 1300 if year >= CENTURY_PIVOT else 1400
    return year, (None if found.group(2) else year)


def _gearbox(text: _Text) -> Gearbox | None:
    if text.take(_AUTOMATIC):
        return Gearbox.AUTOMATIC
    return Gearbox.MANUAL if text.take(_MANUAL) else None


def _city(text: _Text, known_cities: Collection[str]) -> str | None:
    padded = f" {text.remaining} "
    for city in sorted(known_cities, key=len, reverse=True):
        normalized = normalize_persian(city)
        if normalized and f" {normalized} " in padded:
            text.remaining = padded.replace(f" {normalized} ", " ", 1)
            return city
    return None


def _remainder(text: _Text) -> str:
    words = [word for word in text.remaining.split() if word not in _STOP_WORDS]
    return " ".join(words)


def parse_with_rules(query: str, known_cities: Collection[str]) -> SearchIntent:
    text = _Text(normalize_persian(query))
    km_max = _km_max(text)  # before price: «زیر 50 هزار کیلومتر» is mileage
    price_max = _price_max(text)
    year_min, year_max = _years(text)
    gearbox = _gearbox(text)
    only_below_market = text.take(_BELOW_MARKET) is not None
    city = _city(text, known_cities)
    remainder = _remainder(text)
    return SearchIntent(
        vehicles=[VehicleMention(model=remainder)] if remainder else [],
        year_min=year_min,
        year_max=year_max,
        price_max=price_max,
        km_max=km_max,
        cities=[city] if city else [],
        gearbox=gearbox,
        only_below_market=only_below_market,
    )
