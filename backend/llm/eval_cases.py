"""Labelled queries shared by the rules-parser tests and the opt-in live LLM eval.
Each case lists only the fields that must match; vehicle text is checked loosely."""

from dataclasses import dataclass, field
from typing import Any

from enums import Gearbox

MILLION = 1_000_000
BILLION = 1_000_000_000


@dataclass(frozen=True, slots=True)
class EvalCase:
    query: str
    expected: dict[str, Any]
    vehicle_words: tuple[str, ...] = field(default=())


EVAL_CASES: tuple[EvalCase, ...] = (
    EvalCase(
        "۲۰۶ مدل ۹۸ زیر ۸۰۰ میلیون تهران",
        {
            "year_min": 1398,
            "year_max": 1398,
            "price_max": 800 * MILLION,
            "cities": ["تهران"],
        },
        ("206",),
    ),
    EvalCase(
        "دنا پلاس اتومات زیر یک میلیارد کرج",
        {"price_max": BILLION, "cities": ["کرج"], "gearbox": Gearbox.AUTOMATIC},
        ("دنا", "پلاس"),
    ),
    EvalCase("پراید زیر 1.2", {"price_max": 1_200 * MILLION}, ("پراید",)),
    EvalCase(
        "پژو پارس کارکرد زیر ۵۰ هزار کیلومتر",
        {"km_max": 50_000, "price_max": None},
        ("پژو", "پارس"),
    ),
    EvalCase(
        "سمند کم کارکرد اصفهان", {"km_max": 90_000, "cities": ["اصفهان"]}, ("سمند",)
    ),
    EvalCase(
        "کوییک مدل 1402 دنده ای",
        {"year_min": 1402, "gearbox": Gearbox.MANUAL},
        ("کوییک",),
    ),
    EvalCase("تیبا مدل ۹۵ به بالا", {"year_min": 1395, "year_max": None}, ("تیبا",)),
    EvalCase(
        "ساینا ارزان مشهد", {"only_below_market": True, "cities": ["مشهد"]}, ("ساینا",)
    ),
    EvalCase("هوندا ۱۲۵ تا ۸۰ میلیون", {"price_max": 80 * MILLION}, ("هوندا",)),
    EvalCase("زیر ۵۰۰ میلیون شیراز", {"price_max": 500 * MILLION, "cities": ["شیراز"]}),
)
