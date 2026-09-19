"""Masks sellers' phone numbers in free text (spec 3 §3.5). Stored data is never
changed; only what leaves the API through `ListingDetail.description`."""

import re

PHONE_PLACEHOLDER = "شماره در آگهی دیوار"

_DIGIT = r"[0-9۰-۹٠-٩]"
_SEPARATOR = r"[\s\-.]{0,2}"
_PREFIX = r"(?:\+?(?:98|۹۸|٩٨)|[0۰٠])"
# An Iranian number is the prefix (0 or +98) followed by ten more digits, in any digit
# script, with optional spaces/dashes/dots between them: mobiles (09xx…) and landlines
# (0xx…) alike. Digit boundaries on both sides keep prices, km and years untouched.
_PHONE = re.compile(
    rf"(?<!{_DIGIT}){_PREFIX}{_SEPARATOR}(?:{_DIGIT}{_SEPARATOR}){{9}}{_DIGIT}(?!{_DIGIT})"
)


def mask_phone_numbers(text: str) -> str:
    return _PHONE.sub(PHONE_PLACEHOLDER, text)
