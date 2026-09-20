import pytest

from enums import (
    BodyCondition,
    Category,
    DocumentStatus,
    Fuel,
    Gearbox,
    PriceType,
    Source,
)
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


def test_a_row_without_a_source_column_is_divar() -> None:
    # The Divar export predates the column, so its absence is not an unknown source.
    assert map_row(BASE_ROW).listing.source is Source.DIVAR


def test_maps_the_source_column_of_the_newer_crawls() -> None:
    mapped = map_row(row(source="hamrah-mechanic"))
    assert mapped.listing.source is Source.HAMRAH_MECHANIC


def test_an_unrecognised_source_aborts_the_run() -> None:
    with pytest.raises(UnknownValueError):
        map_row(row(source="cardealer"))


def test_reads_the_price_type_stated_by_the_source() -> None:
    mapped = map_row(row(source="bama", price_type_raw="negotiable"))
    assert mapped.listing.price_type is PriceType.NEGOTIABLE


def test_divar_instalment_flag_becomes_a_price_type() -> None:
    # Divar states no price type; it only flags that instalments are on offer.
    assert map_row(row(**{"فروش قسطی": "دارد"})).listing.price_type is (
        PriceType.INSTALLMENT
    )


def test_price_type_is_unknown_when_nobody_states_one() -> None:
    assert map_row(BASE_ROW).listing.price_type is None


def test_maps_both_document_vocabularies() -> None:
    divar = map_row(row(**{"وضعیت سند و مدارک": "سند در رهن"})).listing
    hamrah = map_row(
        row(source="hamrah-mechanic", **{"وضعیت سند و مدارک": "تک برگی"})
    ).listing
    assert (divar.document_status, hamrah.document_status) == (
        DocumentStatus.MORTGAGED,
        DocumentStatus.SINGLE_PAGE,
    )


def test_an_uninformative_document_value_is_recorded_as_unknown() -> None:
    assert map_row(row(**{"وضعیت سند و مدارک": "سایر"})).listing.document_status is None
