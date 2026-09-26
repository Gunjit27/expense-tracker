"""Spending analytics: the SQL aggregations behind /ai/ask, with Ollama stubbed out.

Assertions check the numbers the model is given, not the exact wording of the
context strings, so the tests survive changes to how questions are routed.
"""
from datetime import date

import pytest
import requests

from app import ai
from app.auth import decode_token


@pytest.fixture
def spending(add_expense):
    today = date.today().isoformat()
    add_expense(amount="500", category="Food", payment_method="UPI", expense_date=today)
    add_expense(amount="1500", category="Bills", payment_method="Bank Transfer", expense_date=today)
    add_expense(amount="200", category="Food", payment_method="Cash", expense_date="2020-01-01")


def user_id(auth):
    return decode_token(auth["Authorization"].split()[1])


def test_context_top_expenses(client, auth, spending):
    ctx = ai.fetch_context("What was my biggest expense?", user_id(auth))
    assert ctx.index("1500") < ctx.index("500") < ctx.index("200")


def test_context_spending_by_category(client, auth, spending):
    ctx = ai.fetch_context("Which category do I spend on?", user_id(auth))
    assert "Bills" in ctx and "1500.00" in ctx
    assert "Food" in ctx and "700.00" in ctx


def test_context_by_payment_method(client, auth, spending):
    ctx = ai.fetch_context("How much via UPI?", user_id(auth))
    assert "Bank Transfer" in ctx and "1500.00" in ctx


def test_context_this_month(client, auth, spending):
    ctx = ai.fetch_context("How much did I spend this month?", user_id(auth))
    assert "2000.00" in ctx and "2200.00" not in ctx


def test_context_all_time_fallback(client, auth, spending):
    ctx = ai.fetch_context("Summarise my spending", user_id(auth))
    assert "2200.00" in ctx


def test_context_excludes_other_users(client, auth, other_auth, spending):
    ctx = ai.fetch_context("Summarise my spending", user_id(other_auth))
    assert "2200.00" not in ctx and "1500.00" not in ctx


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


def test_ask_sends_context_to_ollama(client, auth, spending, monkeypatch):
    captured = {}

    def fake_post(url, json, timeout):
        captured.update(json)
        return FakeResponse({"response": "  You spent ₹2200 in total.  "})

    monkeypatch.setattr(ai.requests, "post", fake_post)
    resp = client.post("/ai/ask", headers=auth, json={"question": "Summarise my spending"})
    assert resp.status_code == 200
    assert resp.json() == {"answer": "You spent ₹2200 in total."}
    assert "2200.00" in captured["prompt"]


def test_ask_returns_503_when_ollama_is_down(client, auth, monkeypatch):
    def fake_post(*args, **kwargs):
        raise requests.ConnectionError("refused")

    monkeypatch.setattr(ai.requests, "post", fake_post)
    resp = client.post("/ai/ask", headers=auth, json={"question": "anything"})
    assert resp.status_code == 503


def test_ask_requires_auth(client):
    assert client.post("/ai/ask", json={"question": "hi"}).status_code in (401, 403)
