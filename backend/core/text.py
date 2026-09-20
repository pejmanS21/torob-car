"""Persian text helpers. `normalize_persian` is the ONLY normaliser: ingest and
query parsing must both go through it, otherwise trigram matching silently degrades."""

from collections.abc import Mapping
from datetime import date

_PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
_ASCII_DIGITS = "0123456789"
_NOWRUZ = (3, 21)
_JALALI_OFFSET_AFTER_NOWRUZ = 621
_JALALI_OFFSET_BEFORE_NOWRUZ = 622

# The single source of truth for the oldest Jalali year the system will accept.
# Ingest uses it to bound what a listing's year can be; search uses it to bound
# what a filter's year can be — they must agree, or an ingestable listing could
# become unsearchable (see ingest/normalizers.py and schemas/search.py).
MIN_JALALI_YEAR = 1300

_TO_ASCII_DIGITS = str.maketrans(
    _PERSIAN_DIGITS + _ARABIC_DIGITS, _ASCII_DIGITS + _ASCII_DIGITS
)
_TO_PERSIAN_DIGITS = str.maketrans(_ASCII_DIGITS, _PERSIAN_DIGITS)
_CHARACTER_FIXES = str.maketrans(
    {
        "ي": "ی",  # Arabic yeh
        "ك": "ک",  # Arabic kaf
        "‌": " ",  # ZWNJ → space
        "‏": None,  # right-to-left mark
        "‎": None,  # left-to-right mark
    }
)


def to_ascii_digits(text: str) -> str:
    return text.translate(_TO_ASCII_DIGITS)


def to_persian_digits(value: int | str) -> str:
    return str(value).translate(_TO_PERSIAN_DIGITS)


def normalize_persian(text: str) -> str:
    fixed = to_ascii_digits(text.translate(_CHARACTER_FIXES)).lower()
    return " ".join(fixed.split())


def jalali_year(moment: date) -> int:
    # ponytail: year-only conversion, exact to within Nowruz drifting by a day;
    # pull in a calendar library only if a full Jalali date is ever needed.
    after_nowruz = (moment.month, moment.day) >= _NOWRUZ
    offset = (
        _JALALI_OFFSET_AFTER_NOWRUZ if after_nowruz else _JALALI_OFFSET_BEFORE_NOWRUZ
    )
    return moment.year - offset


# Car names reach us in both scripts: the catalog has «بنز کلاس G جی 63» while people
# type "g class". Trigram similarity cannot see that «کلاس» and "class" are the same
# word, so the query is rewritten into both scripts before the catalog is searched.
# Only pairs actually present in the crawled data belong here — add one when a real
# query misses because of the split, never on speculation.
CROSS_SCRIPT_WORDS: Mapping[str, str] = {
    "class": "کلاس",
    "benz": "بنز",
    "mercedes": "مرسدس",
    "coupe": "کوپه",
    "sedan": "سدان",
}
_SCRIPT_EQUIVALENTS: Mapping[str, str] = {
    **CROSS_SCRIPT_WORDS,
    **{persian: latin for latin, persian in CROSS_SCRIPT_WORDS.items()},
}


def script_variants(query: str) -> tuple[str, ...]:
    """The query as written, plus the same query with every known word swapped to the
    other script. One extra variant at most, and never fewer than the original."""
    words = query.split()
    swapped = [_SCRIPT_EQUIVALENTS.get(word, word) for word in words]
    if swapped == words:
        return (query,)
    return (query, " ".join(swapped))
