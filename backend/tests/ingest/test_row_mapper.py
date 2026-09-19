import pytest

from enums import BodyCondition, Category, Fuel, Gearbox
from ingest.column_maps import UnknownValueError
from ingest.row_mapper import NULLED_KM, NULLED_PRICE, RowRejectedError, map_row

BASE_ROW = {
    "token": "tok001",
    "url": "https://divar.ir/v/-/tok001",
    "title": "پژو ۲۰۶ تیپ ۲ مدل ۹۸",
    "description": "متن آگهی",
    "city": "تهران",
    "posted_raw": "۳ ساعت پیش در تهران، پونک",
    "latitude": "35.76",
    "longitude": "51.33",
    "image_urls": "https://a/1.webp | https://a/2.webp",
    "thumbnail_urls": "https://a/t1.webp",
    "fetched_at": "1789660000",
    "webengage_cat_2": "cars",
    "webengage_cat_3": "light",
    "webengage_business_type": "personal",
    "برند و مدل": "پژو 206 تیپ ۲",
    "قیمت پایه": "‏۷۸۰,۰۰۰,۰۰۰ تومان",
    "مدل (سال تولید)": "۱۳۹۸ - ۲۰۱۹",
    "کارکرد": "۶۲۰۰۰",
    "گیربکس": "دنده‌ای",
    "نوع سوخت": "بنزین",
    "رنگ": "سفید",
    "مهلت بیمهٔ شخص ثالث": "۸ ماه",
    "مالکیت خودرو": "شخصی",
}


def row(**overrides: str) -> dict[str, str]:
    return {**BASE_ROW, **overrides}


def test_maps_a_passenger_car() -> None:
    mapped = map_row(BASE_ROW)
    listing = mapped.listing
    assert mapped.nulled == ()
    assert (listing.category, listing.brand, listing.model) == (
        Category.LIGHT,
        "پژو",
        "پژو 206",
    )
    assert (listing.price, listing.year, listing.km) == (780_000_000, 1398, 62_000)
    assert (listing.gearbox, listing.fuel) == (Gearbox.MANUAL, Fuel.PETROL)
    assert listing.title_normalized == "پژو 206 تیپ 2 مدل 98"
    assert listing.district == "پونک"
    assert listing.insurance_months == 8
    assert listing.is_dealer is False
    assert listing.image_urls == ["https://a/1.webp", "https://a/2.webp"]
    assert listing.attributes == {"مالکیت خودرو": "شخصی"}


def test_heavy_vehicle_reads_its_own_columns_and_has_no_catalog_entry() -> None:
    heavy = row(
        **{
            "webengage_cat_3": "heavy",
            "برند و مدل": "",
            "قیمت پایه": "",
            "قیمت": "‏۱,۷۰۰,۰۰۰,۰۰۰ تومان",
            "مدل (سال تولید)": "",
            "سال ساخت": "۱۳۸۸",
            "نوع وسیلهٔ نقلیه": "کامیون یا کامیونت",
            "وضعیت بدنه": "کاملا سالم",
        }
    )
    listing = map_row(heavy).listing
    assert listing.category is Category.HEAVY
    assert (listing.trim, listing.brand, listing.model) == (None, None, None)
    assert (listing.price, listing.year) == (1_700_000_000, 1388)
    assert listing.vehicle_type == "کامیون یا کامیونت"
    assert listing.body_condition is BodyCondition.INTACT


def test_motorcycle_is_detected_from_level_two() -> None:
    bike = row(webengage_cat_3="", webengage_cat_2="motorcycles")
    assert map_row(bike).listing.category is Category.MOTORCYCLE


def test_rental_keeps_the_rent_amount_out_of_price() -> None:
    rental = row(webengage_cat_3="rental", price_raw="‏۱۵,۰۰۰,۰۰۰ تومان")
    listing = map_row(rental).listing
    assert listing.price is None
    assert listing.attributes["price_raw"] == "‏۱۵,۰۰۰,۰۰۰ تومان"


def test_placeholder_price_and_capped_km_are_nulled_and_reported() -> None:
    mapped = map_row(row(**{"قیمت پایه": "‏۱,۰۰۰ تومان", "کارکرد": "۱۰۰۰۰۰۰"}))
    assert mapped.listing.price is None and mapped.listing.km is None
    assert set(mapped.nulled) == {NULLED_PRICE, NULLED_KM}


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"token": ""}, "missing_token"),
        ({"title": " "}, "missing_title"),
        ({"city": ""}, "missing_city"),
        ({"webengage_cat_3": "", "webengage_cat_2": "boats"}, "unknown_category"),
    ],
)
def test_unusable_rows_are_rejected(overrides: dict[str, str], reason: str) -> None:
    with pytest.raises(RowRejectedError) as rejected:
        map_row(row(**overrides))
    assert rejected.value.reason == reason


def test_unknown_vocabulary_value_aborts_loudly() -> None:
    with pytest.raises(UnknownValueError) as error:
        map_row(row(**{"نوع سوخت": "هیدروژن"}))
    assert error.value.context == {"column": "نوع سوخت", "value": "هیدروژن"}
