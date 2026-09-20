from datetime import date

import pytest

from core.text import (
    jalali_year,
    normalize_persian,
    script_variants,
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


def test_script_variants_rewrites_known_words_into_the_other_script() -> None:
    # The catalog spells this car «بنز کلاس G جی 63», so "g class" has to reach «کلاس».
    assert script_variants("g class") == ("g class", "g کلاس")
    assert script_variants("جی کلاس") == ("جی کلاس", "جی class")


def test_script_variants_leave_an_unknown_query_alone() -> None:
    assert script_variants("پژو 206") == ("پژو 206",)
    assert script_variants("") == ("",)
