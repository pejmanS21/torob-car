from datetime import UTC, datetime, timedelta

import pytest

from ingest import normalizers
from ingest.normalizers import BrandModel

FETCHED_AT = datetime(2026, 9, 17, 20, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("‏۴,۳۰۰,۰۰۰,۰۰۰ تومان", 4_300_000_000),
        ("‏۱۰,۰۰۰,۰۰۰ تومان", 10_000_000),
        ("‏۵,۵۰۰,۰۰۰ تومان", None),  # placeholder below the plausible floor
        ("‏۱,۰۰۰ تومان", None),
        ("", None),
    ],
)
def test_parse_price(raw: str, expected: int | None) -> None:
    assert normalizers.parse_price(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("۶۲۰۰۰", 62_000), ("۰", 0), ("۱۰۰۰۰۰۰", None), ("", None)],
)
def test_parse_km_keeps_zero_and_drops_the_capped_value(
    raw: str, expected: int | None
) -> None:
    assert normalizers.parse_km(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("۱۴۰۱ - ۲۰۲۲", 1401),
        ("۱۳۹۵", 1395),
        ("قبل از ۱۳۶۶ - قبل از ۱۹۸۷", 1365),
        ("قبل از ۱۳۷۰", 1369),
        ("1,402", 1402),
        ("2010", 1389),  # Gregorian year converted
        ("", None),
        ("نامشخص", None),
    ],
)
def test_parse_year(raw: str, expected: int | None) -> None:
    assert normalizers.parse_year(raw) == expected


def test_parse_insurance_months() -> None:
    assert normalizers.parse_insurance_months("۱۲ ماه") == 12
    assert normalizers.parse_insurance_months("") is None
    assert normalizers.parse_insurance_months("۴۰ ماه") is None


@pytest.mark.parametrize(
    ("phrase", "hours"),
    [
        ("نیم ساعت پیش", 0.5),
        ("۳ ساعت پیش", 3),
        ("دیروز", 24),
        ("پریروز", 48),
        ("۴ روز پیش", 96),
        ("هفته پیش", 168),
        ("۲ هفته پیش", 336),
        ("ماه پیش", 720),
        ("۲ ماه پیش", 1440),
        ("سال پیش", 8760),
    ],
)
def test_parse_posted_at(phrase: str, hours: float) -> None:
    posted_at = normalizers.parse_posted_at(f"{phrase} در کرج، اسدآباد", FETCHED_AT)
    assert posted_at == FETCHED_AT - timedelta(hours=hours)


def test_parse_posted_at_returns_none_for_an_unknown_phrase() -> None:
    assert normalizers.parse_posted_at("لحظاتی پیش در تهران", FETCHED_AT) is None


@pytest.mark.parametrize(
    ("posted_raw", "district"),
    [
        ("۴ روز پیش در کرج، اسدآباد، خ مهر یکم", "اسدآباد"),
        ("دیروز در تهران، شهرک شریعتی", "شهرک شریعتی"),
        ("دیروز در تهران", None),
        ("", None),
    ],
)
def test_parse_district(posted_raw: str, district: str | None) -> None:
    assert normalizers.parse_district(posted_raw) == district


@pytest.mark.parametrize(
    ("trim", "expected"),
    [
        ("پژو 206 تیپ ۲", BrandModel("پژو", "پژو 206")),
        ("پراید 131 SE", BrandModel("پراید", "پراید 131")),
        ("ام‌وی‌ام X22 Pro IE", BrandModel("ام وی ام", "ام وی ام x22")),
        ("اس وای ام Galaxy NA 180", BrandModel("اس وای ام", "اس وای ام galaxy")),
        ("ایران خودرو ری را", BrandModel("ایران خودرو", "ایران خودرو ری")),
        ("سایر", BrandModel("سایر", "سایر")),
    ],
)
def test_split_brand_model(trim: str, expected: BrandModel) -> None:
    assert normalizers.split_brand_model(trim) == expected


def test_split_urls() -> None:
    assert normalizers.split_urls("https://a/1.webp | https://a/2.webp") == [
        "https://a/1.webp",
        "https://a/2.webp",
    ]
    assert normalizers.split_urls("") == []
