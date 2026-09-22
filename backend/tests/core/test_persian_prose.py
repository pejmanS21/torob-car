import pytest

from core.persian_prose import format_persian_prose


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("بهصرفهبودن این خودرو", "به‌صرفه بودن این خودرو"),
        ("به‌صرفه‌بودن این خودرو", "به‌صرفه بودن این خودرو"),
        ("بهصرفهترین و کمکارکرد", "به‌صرفه‌ترین و کم‌کارکرد"),
        ("اين ماشين خوشقیمت است", "این ماشین خوش‌قیمت است"),
        (
            "می‌تونی آگهی‌ها رو ببینی؛ ۲۰۶ تیپ ۲\n۹۷۰ میلیون",
            "می‌تونی آگهی‌ها رو ببینی؛ ۲۰۶ تیپ ۲\n۹۷۰ میلیون",
        ),
        ("کمیته مینا نمیرا کمال G63", "کمیته مینا نمیرا کمال G63"),
    ],
)
def test_display_cleanup_preserves_words_digits_and_half_spaces(
    raw: str, expected: str
) -> None:
    assert format_persian_prose(raw) == expected
    assert format_persian_prose(expected) == expected
