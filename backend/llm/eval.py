"""Opt-in live accuracy check of the intent prompt. Calls the REAL provider, costs
tokens, and is never run in CI:

    uv run python -m llm.eval

Run it before and after editing llm/intent_agent.py, and bump PROMPT_VERSION in
services/query_parser.py when the instructions change."""

import asyncio

from core.config import get_settings
from core.text import normalize_persian
from llm.eval_cases import EVAL_CASES, EvalCase
from llm.intent_agent import build_intent_agent
from llm.model_factory import build_model
from schemas.search import SearchIntent


def score_case(case: EvalCase, intent: SearchIntent) -> tuple[int, int, list[str]]:
    """(fields correct, fields checked, names of the wrong fields)."""
    wrong = [
        name for name, value in case.expected.items() if getattr(intent, name) != value
    ]
    mention = normalize_persian(
        " ".join(
            " ".join(filter(None, (vehicle.brand, vehicle.model, vehicle.trim)))
            for vehicle in intent.vehicles
        )
    )
    if not all(word in mention for word in case.vehicle_words):
        wrong.append("vehicles")
    checked = len(case.expected) + bool(case.vehicle_words)
    return checked - len(wrong), checked, wrong


async def main() -> None:
    model = build_model(get_settings())
    if model is None:
        raise SystemExit("LLM_API_KEY is not set")
    agent = build_intent_agent(model)
    correct = checked = 0
    for case in EVAL_CASES:
        result = await agent.run(normalize_persian(case.query))
        case_correct, case_checked, wrong = score_case(case, result.output)
        correct += case_correct
        checked += case_checked
        print(f"{'ok ' if not wrong else 'BAD'} {case.query}  {wrong or ''}")
    print(f"\nfield accuracy: {correct}/{checked} = {correct / checked:.0%}")


if __name__ == "__main__":
    asyncio.run(main())
