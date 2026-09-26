"""Spending analytics: the SQL aggregations behind /ai/ask, with Ollama stubbed out."""
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
    assert ctx.startswith("Top 5 expenses")
    assert ctx.index("1500") < ctx.index("500") < ctx.index("200")


def test_context_spending_by_category(client, auth, spending):
    ctx = ai.fetch_context("Which category do I spend on?", user_id(auth))
    assert ctx.startswith("Spending by category")
    assert "('Bills', Decimal('1500.00'))" in ctx
    assert "('Food', Decimal('700.00'))" in ctx


def test_context_by_payment_method(client, auth, spending):
    ctx = ai.fetch_context("How much via UPI?", user_id(auth))
    assert ctx.startswith("Spending by payment method")
    assert "('Bank Transfer', Decimal('1500.00'), 1)" in ctx


def test_context_this_month(client, auth, spending):
    ctx = ai.fetch_context("How much did I spend this month?", user_id(auth))
    assert ctx == "Current month total and transactions: (Decimal('2000.00'), 2)"


def test_context_all_time_fallback(client, auth, spending):
    ctx = ai.fetch_context("Summarise my spending", user_id(auth))
    assert ctx == "All-time total and transactions: (Decimal('2200.00'), 3)"


def test_context_excludes_other_users(client, auth, other_auth, spending):
    ctx = ai.fetch_context("Summarise my spending", user_id(other_auth))
    assert ctx == "All-time total and transactions: (Decimal('0'), 0)"


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
    assert "All-time total and transactions: (Decimal('2200.00'), 3)" in captured["prompt"]
    assert captured["stream"] is False


def test_ask_returns_503_when_ollama_is_down(client, auth, monkeypatch):
    def fake_post(*args, **kwargs):
        raise requests.ConnectionError("refused")

    monkeypatch.setattr(ai.requests, "post", fake_post)
    resp = client.post("/ai/ask", headers=auth, json={"question": "anything"})
    assert resp.status_code == 503


def test_ask_requires_auth(client):
    assert client.post("/ai/ask", json={"question": "hi"}).status_code in (401, 403)
