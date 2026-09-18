from datetime import date

import pytest

from core.text import (
    jalali_year,
    normalize_persian,
    to_ascii_digits,
    to_persian_digits,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("پژو ۲۰۶ تیپ ۲", "پژو 206 تیپ 2"),
        ("كيا  ريو", "کیا ریو"),  # Arabic kaf/yeh + double space
        ("ام‌وی‌ام X22 Pro", "ام وی ام x22 pro"),  # ZWNJ → space, Latin lowercased
        ("‏۴,۳۰۰,۰۰۰ تومان", "4,300,000 تومان"),  # RLM stripped
        ("٢٠٦", "206"),  # Arabic-Indic digits
        ("  ", ""),
    ],
)
def test_normalize_persian(raw: str, expected: str) -> None:
    assert normalize_persian(raw) == expected


def test_to_ascii_digits_keeps_other_characters() -> None:
    assert to_ascii_digits("مدل ۱۳۹۸") == "مدل 1398"


def test_to_persian_digits_formats_ints_and_strings() -> None:
    assert to_persian_digits(1398) == "۱۳۹۸"
    assert to_persian_digits("1.2") == "۱.۲"


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        (date(2026, 9, 18), 1405),
        (date(2026, 3, 21), 1405),  # Nowruz
        (date(2026, 3, 20), 1404),
        (date(2027, 1, 1), 1405),
    ],
)
def test_jalali_year(moment: date, expected: int) -> None:
    assert jalali_year(moment) == expected
