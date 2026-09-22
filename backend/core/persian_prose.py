"""Presentation cleanup for assistant prose; never use search normalization here.

Search normalization removes half-spaces and changes digits. Display text must
keep both. Corrections below are deliberately narrow, not a general word splitter.
"""

import re
import unicodedata

_LETTERS = str.maketrans({"ي": "ی", "ك": "ک"})
_VALUE_WORD = re.compile(
    r"(?<![\w\u200c])به[ \u200c]*صرفه(?:[ \u200c]*(ترین|تر|بودن))?(?![\w\u200c])"
)
_COMPOUNDS = {
    "کمکارکرد": "کم‌کارکرد",
    "خوشقیمت": "خوش‌قیمت",
    "بیکیفیت": "بی‌کیفیت",
}
_JOINED_COMPOUNDS = re.compile(r"\b(?:" + "|".join(_COMPOUNDS) + r")\b")


def _value_word(match: re.Match[str]) -> str:
    suffix = match.group(1)
    if suffix == "بودن":
        return "به‌صرفه بودن"
    return "به‌صرفه" + ("‌" + suffix if suffix else "")


def format_persian_prose(text: str) -> str:
    text = unicodedata.normalize("NFC", text).translate(_LETTERS)
    text = _VALUE_WORD.sub(_value_word, text)
    return _JOINED_COMPOUNDS.sub(lambda match: _COMPOUNDS[match.group()], text)
