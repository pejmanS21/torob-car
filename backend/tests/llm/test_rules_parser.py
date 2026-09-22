import pytest

from enums import Gearbox
from llm.eval_cases import EVAL_CASES, EvalCase
from llm.rules_parser import parse_with_rules

KNOWN_CITIES = ("تهران", "کرج", "اصفهان", "مشهد", "شیراز", "اسلام‌شهر")


@pytest.mark.parametrize("case", EVAL_CASES, ids=[case.query for case in EVAL_CASES])
def test_rules_parser_extracts_the_labelled_fields(case: EvalCase) -> None:
    intent = parse_with_rules(case.query, KNOWN_CITIES)
    actual = {name: getattr(intent, name) for name in case.expected}
    assert actual == case.expected
    mention = " ".join(vehicle.model or "" for vehicle in intent.vehicles)
    assert all(word in mention for word in case.vehicle_words)


def test_recognised_clauses_never_leak_into_the_vehicle_mention() -> None:
    intent = parse_with_rules(
        "یه ۲۰۶ مدل ۹۸ زیر ۸۰۰ میلیون تو تهران میخوام", KNOWN_CITIES
    )
    assert [vehicle.model for vehicle in intent.vehicles] == ["206"]


def test_city_with_zwnj_is_matched_after_normalisation() -> None:
    assert parse_with_rules("پراید اسلام شهر", KNOWN_CITIES).cities == ["اسلام‌شهر"]


def test_empty_query_is_an_empty_intent() -> None:
    intent = parse_with_rules("   ", KNOWN_CITIES)
    assert intent.vehicles == [] and intent.price_max is None


@pytest.mark.parametrize("gearbox", ["اتمات", "اتماتیک", "اتومات", "اتوماتیک"])
def test_dena_plus_automatic_keeps_gearbox_out_of_vehicle_name(gearbox: str) -> None:
    intent = parse_with_rules(f"دنا پلاس {gearbox}", KNOWN_CITIES)
    assert intent.gearbox is Gearbox.AUTOMATIC
    assert [vehicle.model for vehicle in intent.vehicles] == ["دنا پلاس"]
