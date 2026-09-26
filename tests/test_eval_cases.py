"""Keep the router eval set valid: every expected answer must itself be a valid tool call."""
import pytest

from app.ai_tools import parse_tool_call
from evals.run_router_eval import CASES, CATEGORIES, load_cases

cases = load_cases(CASES)


@pytest.mark.parametrize("case", cases, ids=[c["question"] for c in cases])
def test_expected_call_is_valid(case):
    parse_tool_call(case["tool"], case["args"], CATEGORIES)


def test_questions_are_unique():
    questions = [c["question"].lower() for c in cases]
    assert len(questions) == len(set(questions))
