"""The AI assistant: tool-call validation, the SQL behind each tool, and /ai/ask with a scripted LLM.

Ollama is never called. A ScriptedLLM returns canned chat messages, so these
tests cover everything around the model; how well a real model picks tools is
measured separately by evals/run_router_eval.py.
"""
from datetime import date

import pytest

from app import ai
from app.ai_tools import TOOL_SPECS, ToolArgError, parse_tool_call, resolve_dates, run_tool
from app.auth import decode_token
from app.database import get_conn
from app.llm import LLMError
from app.main import app

TODAY = date(2026, 9, 15)
CATEGORIES = ["Bills", "Food", "Shopping", "Transport"]


class ScriptedLLM:
    """Returns the queued messages in order and records every request."""

    def __init__(self, *messages):
        self.messages = list(messages)
        self.requests = []

    def chat(self, messages, tools=None):
        self.requests.append({"messages": list(messages), "tools": tools})
        return self.messages.pop(0)


def tool_call(name, **arguments):
    return {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": name, "arguments": arguments}}]}


def text(content):
    return {"role": "assistant", "content": content}


@pytest.fixture
def spending(add_expense):
    add_expense(amount="500", category="Food", payment_method="UPI", expense_date="2026-09-10")
    add_expense(amount="1500", category="Bills", payment_method="Bank Transfer", expense_date="2026-09-01")
    add_expense(amount="300", category="Food", payment_method="Cash", expense_date="2026-08-20")
    add_expense(amount="200", category="Transport", payment_method="UPI", expense_date="2025-12-31")


def user_id(auth):
    return decode_token(auth["Authorization"].split()[1])


def run(auth, name, **args):
    with get_conn() as conn:
        return run_tool(conn, user_id(auth), parse_tool_call(name, args, CATEGORIES), TODAY)


# Tool-call validation

def test_tool_specs_are_flat_for_small_models():
    for spec in TOOL_SPECS:
        for prop in spec["function"]["parameters"]["properties"].values():
            assert "anyOf" not in prop and "$ref" not in prop


def test_category_is_matched_case_insensitively():
    call = parse_tool_call("total_spend", {"category": "food"}, CATEGORIES)
    assert call.args.category == "Food"


def test_unknown_category_error_lists_valid_ones():
    with pytest.raises(ToolArgError, match="Bills, Food, Shopping, Transport"):
        parse_tool_call("total_spend", {"category": "Groceries"}, CATEGORIES)


def test_unknown_tool_is_rejected():
    with pytest.raises(ToolArgError, match="Unknown tool"):
        parse_tool_call("run_sql", {"query": "DROP TABLE users"}, CATEGORIES)


def test_blank_arguments_are_treated_as_unset():
    call = parse_tool_call("total_spend", {"category": "", "payment_method": "null", "period": "this_month"}, CATEGORIES)
    assert call.args.category is None and call.args.payment_method is None


def test_arguments_as_json_string_are_accepted():
    call = parse_tool_call("find_expenses", '{"order_by": "date", "limit": "3"}', CATEGORIES)
    assert call.args.order_by == "date" and call.args.limit == 3


@pytest.mark.parametrize("args", [
    {"period": "month"},
    {"period": "custom"},
    {"period": "custom", "start_date": "2026-09-10", "end_date": "2026-09-01"},
    {"payment_method": "Crypto"},
    {"month": "2026-13"},
])
def test_invalid_filters_are_rejected(args):
    with pytest.raises(ToolArgError):
        parse_tool_call("total_spend", args, CATEGORIES)


def test_limit_is_capped():
    with pytest.raises(ToolArgError):
        parse_tool_call("find_expenses", {"limit": 500}, CATEGORIES)


@pytest.mark.parametrize("args, expected", [
    ({"period": "all_time"}, (None, None)),
    ({"period": "this_week"}, (date(2026, 9, 14), TODAY)),
    ({"period": "last_7_days"}, (date(2026, 9, 9), TODAY)),
    ({"period": "this_month"}, (date(2026, 9, 1), TODAY)),
    ({"period": "last_month"}, (date(2026, 8, 1), date(2026, 8, 31))),
    ({"period": "last_year"}, (date(2025, 1, 1), date(2025, 12, 31))),
    ({"period": "month", "month": "2024-02"}, (date(2024, 2, 1), date(2024, 2, 29))),
    ({"month": "2026-07"}, (date(2026, 7, 1), date(2026, 7, 31))),
])
def test_periods_resolve_to_date_ranges(args, expected):
    assert resolve_dates(parse_tool_call("total_spend", args, CATEGORIES).args, TODAY) == expected


def test_last_month_in_january_wraps_to_december():
    args = parse_tool_call("total_spend", {"period": "last_month"}, CATEGORIES).args
    assert resolve_dates(args, date(2026, 1, 10)) == (date(2025, 12, 1), date(2025, 12, 31))


# SQL behind each tool

def test_total_spend_all_time(client, auth, spending):
    assert run(auth, "total_spend") | {"date_range": None} == {"date_range": None, "total": 2500.0, "transactions": 4}


def test_total_spend_with_filters(client, auth, spending):
    assert run(auth, "total_spend", period="this_month")["total"] == 2000.0
    assert run(auth, "total_spend", category="Food")["total"] == 800.0
    assert run(auth, "total_spend", payment_method="UPI", period="this_year")["total"] == 500.0
    assert run(auth, "total_spend", period="custom", start_date="2026-08-01", end_date="2026-09-05")["total"] == 1800.0


def test_breakdown_by_category_is_sorted_by_total(client, auth, spending):
    groups = run(auth, "spend_breakdown", group_by="category")["groups"]
    assert [(g["category"], g["total"]) for g in groups] == [("Bills", 1500.0), ("Food", 800.0), ("Transport", 200.0)]


def test_breakdown_by_payment_method(client, auth, spending):
    groups = run(auth, "spend_breakdown", group_by="payment_method", period="this_month")["groups"]
    assert [(g["payment_method"], g["total"]) for g in groups] == [("Bank Transfer", 1500.0), ("UPI", 500.0)]


def test_breakdown_by_month_is_chronological(client, auth, spending):
    groups = run(auth, "spend_breakdown", group_by="month")["groups"]
    assert [g["month"] for g in groups] == ["2025-12", "2026-08", "2026-09"]


def test_find_biggest_and_most_recent(client, auth, spending):
    biggest = run(auth, "find_expenses", order_by="amount", limit=2)["expenses"]
    assert [e["amount"] for e in biggest] == [1500.0, 500.0]
    recent = run(auth, "find_expenses", order_by="date", category="Food")["expenses"]
    assert [e["date"] for e in recent] == ["2026-09-10", "2026-08-20"]


def test_tools_only_see_the_current_users_data(client, auth, other_auth, spending):
    assert run(other_auth, "total_spend") | {"date_range": None} == {"date_range": None, "total": 0.0, "transactions": 0}
    assert run(other_auth, "find_expenses")["expenses"] == []


# Planning loop

def test_plan_returns_validated_call():
    llm = ScriptedLLM(tool_call("total_spend", period="last_month", category="food"))
    call, attempts = ai.plan("Food spend last month?", TODAY, CATEGORIES, llm)
    assert (call.name, call.args.category, attempts) == ("total_spend", "Food", 1)
    assert llm.requests[0]["tools"] == TOOL_SPECS
    assert "Tuesday, 15 September 2026" in llm.requests[0]["messages"][0]["content"]


def test_plan_feeds_validation_errors_back_for_one_retry():
    llm = ScriptedLLM(
        tool_call("total_spend", category="Groceries"),
        tool_call("total_spend", category="Food"),
    )
    call, attempts = ai.plan("Groceries total?", TODAY, CATEGORIES, llm)
    assert (call.args.category, attempts) == ("Food", 2)
    feedback = llm.requests[1]["messages"][-1]
    assert feedback["role"] == "tool" and "Unknown category 'Groceries'" in feedback["content"]


def test_plan_gives_up_after_max_attempts():
    llm = ScriptedLLM(text("You spent a lot."), text("Still no tool."))
    with pytest.raises(ai.PlanningError):
        ai.plan("anything", TODAY, CATEGORIES, llm)


# /ai/ask endpoint

@pytest.fixture
def use_llm():
    def _use(llm):
        app.dependency_overrides[ai.get_llm] = lambda: llm
        return llm
    yield _use
    app.dependency_overrides.pop(ai.get_llm, None)


def test_ask_runs_the_chosen_tool_and_answers_from_its_data(client, auth, spending, use_llm):
    llm = use_llm(ScriptedLLM(
        tool_call("spend_breakdown", group_by="category"),
        text("  Bills is your top category at ₹1500.  "),
    ))
    resp = client.post("/ai/ask", headers=auth, json={"question": "Top category?"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["answer"] == "Bills is your top category at ₹1500."
    assert body["tool"] == "spend_breakdown" and body["arguments"]["group_by"] == "category"
    assert body["data"]["groups"][0] == {"category": "Bills", "total": 1500.0, "transactions": 1}
    answer_prompt = llm.requests[1]["messages"][-1]["content"]
    assert "1500.0" in answer_prompt and llm.requests[1]["tools"] is None


def test_ask_offers_the_users_own_categories(client, auth, use_llm):
    client.post("/categories", headers=auth, json={"name": "Rent"})
    llm = use_llm(ScriptedLLM(tool_call("total_spend"), text("₹0")))
    client.post("/ai/ask", headers=auth, json={"question": "Total?"})
    assert "Bills, Food, Rent, Shopping, Transport" in llm.requests[0]["messages"][0]["content"]


def test_ask_returns_422_when_no_valid_tool_call(client, auth, use_llm):
    use_llm(ScriptedLLM(text("no"), text("still no")))
    assert client.post("/ai/ask", headers=auth, json={"question": "hello"}).status_code == 422


def test_ask_returns_503_when_ollama_is_down(client, auth, use_llm):
    class DownLLM:
        def chat(self, messages, tools=None):
            raise LLMError("Ollama is unavailable: refused")

    use_llm(DownLLM())
    resp = client.post("/ai/ask", headers=auth, json={"question": "anything"})
    assert resp.status_code == 503


def test_ask_rejects_empty_question(client, auth):
    assert client.post("/ai/ask", headers=auth, json={"question": ""}).status_code == 422


def test_ask_requires_auth(client):
    assert client.post("/ai/ask", json={"question": "hi"}).status_code in (401, 403)
