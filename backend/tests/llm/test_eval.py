from llm.eval import score_case
from llm.eval_cases import EVAL_CASES
from schemas.search import SearchIntent, VehicleMention

CASE = EVAL_CASES[0]  # «۲۰۶ مدل ۹۸ زیر ۸۰۰ میلیون تهران»


def test_score_case_counts_correct_fields_and_names_the_wrong_ones() -> None:
    perfect = SearchIntent(
        vehicles=[VehicleMention(brand="پژو", model="۲۰۶")], **CASE.expected
    )
    assert score_case(CASE, perfect) == (5, 5, [])
    flawed = perfect.model_copy(update={"cities": [], "vehicles": []})
    assert score_case(CASE, flawed) == (3, 5, ["cities", "vehicles"])
