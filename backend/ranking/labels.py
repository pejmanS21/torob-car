"""Persian near-miss labels, built server-side: the frontend holds no ranking logic."""

from core.text import to_persian_digits
from enums import Fuel, Gearbox

TOMAN_PER_MILLION = 1_000_000
MILLIONS_PER_BILLION = 1_000
KM_PER_THOUSAND = 1_000

PRICE_UNKNOWN = "قیمت توافقی"
KM_UNKNOWN = "کارکرد نامشخص"

GEARBOX_NAMES = {Gearbox.MANUAL: "دنده‌ای", Gearbox.AUTOMATIC: "اتوماتیک"}
FUEL_NAMES = {
    Fuel.PETROL: "بنزینی",
    Fuel.DUAL_FACTORY: "دوگانه‌سوز شرکتی",
    Fuel.DUAL_AFTERMARKET: "دوگانه‌سوز دستی",
    Fuel.HYBRID: "هیبرید",
    Fuel.PLUGIN_HYBRID: "پلاگین هیبرید",
    Fuel.ELECTRIC: "برقی",
    Fuel.DIESEL: "گازوئیلی",
}


def format_toman(amount: int) -> str:
    millions = round(amount / TOMAN_PER_MILLION)
    if millions >= MILLIONS_PER_BILLION:
        billions = f"{millions / MILLIONS_PER_BILLION:.2f}".rstrip("0").rstrip(".")
        return f"{to_persian_digits(billions)} میلیارد"
    return f"{to_persian_digits(millions)} میلیون"


def over_budget(amount: int) -> str:
    return f"{format_toman(amount)} بالاتر از بودجه"


def under_budget(amount: int) -> str:
    return f"{format_toman(amount)} پایین‌تر از بازهٔ قیمت"


def year_gap(years: int, *, older: bool) -> str:
    count = "یک" if years == 1 else to_persian_digits(years)
    return f"{count} سال {'قدیمی‌تر' if older else 'جدیدتر'}"


def over_km(extra_km: int) -> str:
    thousands = max(1, round(extra_km / KM_PER_THOUSAND))
    return f"{to_persian_digits(thousands)} هزار کیلومتر بیشتر از سقف"


def under_km(missing_km: int) -> str:
    thousands = max(1, round(missing_km / KM_PER_THOUSAND))
    return f"{to_persian_digits(thousands)} هزار کیلومتر کمتر از کف"


def farther(distance_km: float, city: str) -> str:
    return f"{to_persian_digits(round(distance_km))} کیلومتر دورتر · {city}"


def other_city(city: str) -> str:
    return f"شهر دیگر · {city}"


def other_trim(trim: str) -> str:
    return f"تیپ متفاوت · {trim}"


def other_model(model: str) -> str:
    return f"مدل متفاوت · {model}"


def gearbox_is(gearbox: Gearbox) -> str:
    return f"گیربکس {GEARBOX_NAMES[gearbox]}"


def fuel_is(fuel: Fuel) -> str:
    return f"سوخت {FUEL_NAMES[fuel]}"


def color_is(color: str) -> str:
    return f"رنگ {color}"
