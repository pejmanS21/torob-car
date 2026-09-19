import pytest

from core.phone import PHONE_PLACEHOLDER, mask_phone_numbers


@pytest.mark.parametrize(
    "raw",
    [
        "تماس ۰۹۱۲۳۴۵۶۷۸۹ فقط",
        "تماس 09123456789 فقط",
        "تماس 0912 345 67 89 فقط",
        "تماس 0912-345-6789 فقط",
        "تماس ٠٩١٢٣٤٥٦٧٨٩ فقط",
        "تماس +989123456789 فقط",
        "تماس 02122334455 فقط",  # landline
    ],
)
def test_phone_numbers_are_replaced(raw: str) -> None:
    assert mask_phone_numbers(raw) == f"تماس {PHONE_PLACEHOLDER} فقط"


@pytest.mark.parametrize(
    "raw",
    [
        "قیمت ۹۷۰,۰۰۰,۰۰۰ تومان",
        "قیمت 1,200,000,000 تومان",
        "کارکرد ۲۷۰۰۰ کیلومتر",
        "مدل ۱۳۹۷ تیپ ۲",
        "شاسی 12345678901234567",  # 17 digits: not a phone
    ],
)
def test_ordinary_numbers_are_untouched(raw: str) -> None:
    assert mask_phone_numbers(raw) == raw


def test_every_number_in_a_description_is_masked() -> None:
    masked = mask_phone_numbers("۰۹۱۲۱۱۱۱۱۱۱ یا ۰۹۳۵۲۲۲۲۲۲۲")
    assert masked == f"{PHONE_PLACEHOLDER} یا {PHONE_PLACEHOLDER}"
