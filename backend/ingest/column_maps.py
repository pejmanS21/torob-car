"""Which CSV column means what, per vehicle category, plus closed value vocabularies.
Vocabulary keys are in `normalize_persian` form (ZWNJ → space)."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from core.text import normalize_persian
from enums import BodyCondition, Category, Fuel, Gearbox
from errors import IngestError

CATEGORY_LEVEL_3 = "webengage_cat_3"
CATEGORY_LEVEL_2 = "webengage_cat_2"
MOTORCYCLES_LEVEL_2 = "motorcycles"
TRIM_COLUMN = "برند و مدل"
KM_COLUMN = "کارکرد"
COLOR_COLUMN = "رنگ"
FUEL_COLUMN = "نوع سوخت"
BODY_COLUMN = "وضعیت بدنه"
INSURANCE_COLUMN = "مهلت بیمهٔ شخص ثالث"
VEHICLE_TYPE_COLUMN = "نوع وسیلهٔ نقلیه"
GEARBOX_COLUMNS = ("گیربکس", "نوع گیربکس")
BUSINESS_TYPE_COLUMN = "webengage_business_type"
PERSONAL_BUSINESS_TYPE = "personal"
RENT_PRICE_COLUMN = "price_raw"

ATTRIBUTE_COLUMNS: tuple[str, ...] = (
    "حجم موتور", "نوع استارت", "نوع کلاچ", "مالکیت خودرو", "مایل به معاوضه",
    "وضعیت سند و مدارک", "وضعیت فنی موتور", "وضعیت فنی موتور و گیربکس",
    "وضعیت لاستیک‌ها", "معاینه فنی", "فروش قسطی", "امکان خرید قسطی",
    "تخفیف بیمهٔ ثالث", "حواله", "مبلغ اجاره", "مبلغ ضمانت",
    "محدودیت کیلومتر (روزانه)", "نوع اجاره", "میزان فابریک بودن قطعات",
    "وضعیت بیمه", "بیمه شخص ثالث", "بیمهٔ شخص ثالث",
)  # fmt: skip


@dataclass(frozen=True, slots=True)
class ColumnMap:
    price: str | None
    year: str


COLUMN_MAPS: Mapping[Category, ColumnMap] = {
    Category.LIGHT: ColumnMap(price="قیمت پایه", year="مدل (سال تولید)"),
    Category.HEAVY: ColumnMap(price="قیمت", year="سال ساخت"),
    Category.MOTORCYCLE: ColumnMap(price="قیمت", year="مدل (سال تولید)"),
    Category.RENTAL: ColumnMap(price=None, year="سال ساخت خودرو"),
    Category.CLASSIC: ColumnMap(price="قیمت", year="مدل (سال ساخت)"),
}

_CATEGORY_BY_LEVEL_3: Mapping[str, Category] = {
    "light": Category.LIGHT,
    "heavy": Category.HEAVY,
    "rental": Category.RENTAL,
    "classic": Category.CLASSIC,
}

GEARBOX_VALUES: Mapping[str, Gearbox] = {
    "دنده ای": Gearbox.MANUAL,
    "اتوماتیک": Gearbox.AUTOMATIC,
}
FUEL_VALUES: Mapping[str, Fuel] = {
    "بنزین": Fuel.PETROL,
    "دوگانه سوز شرکتی": Fuel.DUAL_FACTORY,
    "دوگانه سوز دستی": Fuel.DUAL_AFTERMARKET,
    "هیبرید": Fuel.HYBRID,
    "پلاگین هیبرید": Fuel.PLUGIN_HYBRID,
    "برق": Fuel.ELECTRIC,
    "گازوئیل": Fuel.DIESEL,
}
BODY_VALUES: Mapping[str, BodyCondition] = {
    "کاملا سالم": BodyCondition.INTACT,
    "بدون رنگ": BodyCondition.NO_PAINT,
    "خط و خش جزئی": BodyCondition.MINOR_SCRATCHES,
    "رنگ شدگی جزئی": BodyCondition.PARTIAL_PAINT,
    "رنگ شدگی زیاد": BodyCondition.HEAVY_PAINT,
    "زمین خوردگی": BodyCondition.DROPPED,
    "تصادفی": BodyCondition.ACCIDENT,
    "فابریک": BodyCondition.ORIGINAL,
    "بازسازی شده کامل": BodyCondition.RESTORED,
}


class UnknownValueError(IngestError):
    """A closed-vocabulary column held a value we have no enum for. Aborts the run:
    silently dropping it would hide a schema change in the source data."""

    def __init__(self, column: str, value: str) -> None:
        super().__init__(
            f"Unknown value in column {column!r}", {"column": column, "value": value}
        )


def detect_category(row: Mapping[str, str]) -> Category | None:
    category = _CATEGORY_BY_LEVEL_3.get(row.get(CATEGORY_LEVEL_3, ""))
    if category is None and row.get(CATEGORY_LEVEL_2) == MOTORCYCLES_LEVEL_2:
        return Category.MOTORCYCLE
    return category


def lookup_value[EnumT: StrEnum](
    raw: str, vocabulary: Mapping[str, EnumT], column: str
) -> EnumT | None:
    key = normalize_persian(raw)
    if not key:
        return None
    if key not in vocabulary:
        raise UnknownValueError(column, raw)
    return vocabulary[key]
