import os

# Point the app at a dedicated test database before any app module is imported.
# database.py reads DATABASE_URL at import time, and load_dotenv() never overrides
# variables that are already set.
os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/expense_tracker_test",
)
os.environ.setdefault("JWT_SECRET", "test-secret-at-least-32-bytes-long-for-hs256")

import pytest
from fastapi.testclient import TestClient

from app.database import get_conn
from app.main import app


@pytest.fixture(scope="session")
def client():
    # Entering the context manager runs the startup hook, which applies sql/schema.sql.
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def clean_db(client):
    with get_conn() as conn:
        conn.execute("TRUNCATE expenses, categories, users RESTART IDENTITY CASCADE")
    yield


def register(client, email="user@example.com", password="password123"):
    resp = client.post("/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
def auth(client):
    return register(client)


@pytest.fixture
def other_auth(client):
    return register(client, email="other@example.com")


@pytest.fixture
def categories(client, auth):
    return {c["name"]: c["id"] for c in client.get("/categories", headers=auth).json()}


@pytest.fixture
def add_expense(client, auth, categories):
    def _add(amount="100.00", category="Food", payment_method="UPI",
             expense_date="2026-09-01", description=None, headers=None):
        resp = client.post("/expenses", headers=headers or auth, json={
            "amount": amount,
            "category_id": categories[category],
            "payment_method": payment_method,
            "expense_date": expense_date,
            "description": description,
        })
        assert resp.status_code == 200, resp.text
        return resp.json()
    return _add
