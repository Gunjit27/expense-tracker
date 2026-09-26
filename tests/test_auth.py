from datetime import datetime, timedelta, timezone

import jwt

from app.auth import JWT_ALGORITHM, JWT_SECRET, create_access_token
from app.database import get_conn
from tests.conftest import register


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_register_returns_token_and_seeds_default_categories(client):
    headers = register(client)
    names = [c["name"] for c in client.get("/categories", headers=headers).json()]
    assert names == ["Bills", "Food", "Shopping", "Transport"]


def test_register_stores_hashed_password(client):
    register(client, password="password123")
    with get_conn() as conn:
        stored = conn.execute("SELECT password_hash FROM users").fetchone()[0]
    assert stored != "password123"
    assert stored.startswith("$argon2")


def test_register_duplicate_email_is_case_insensitive(client):
    register(client, email="dup@example.com")
    resp = client.post("/auth/register", json={"email": "DUP@example.com", "password": "password123"})
    assert resp.status_code == 409


def test_register_rejects_short_password(client):
    resp = client.post("/auth/register", json={"email": "a@example.com", "password": "short"})
    assert resp.status_code == 422


def test_register_rejects_invalid_email(client):
    resp = client.post("/auth/register", json={"email": "not-an-email", "password": "password123"})
    assert resp.status_code == 422


def test_login_success(client):
    register(client, email="login@example.com", password="password123")
    resp = client.post("/auth/login", json={"email": "Login@Example.com", "password": "password123"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    assert client.get("/categories", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_login_wrong_password(client):
    register(client, email="login@example.com", password="password123")
    resp = client.post("/auth/login", json={"email": "login@example.com", "password": "wrongpass1"})
    assert resp.status_code == 401


def test_login_unknown_email(client):
    resp = client.post("/auth/login", json={"email": "nobody@example.com", "password": "password123"})
    assert resp.status_code == 401


def test_protected_route_requires_token(client):
    assert client.get("/expenses").status_code in (401, 403)


def test_protected_route_rejects_garbage_token(client):
    resp = client.get("/expenses", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401


def test_protected_route_rejects_expired_token(client, auth):
    expired = jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        JWT_SECRET, algorithm=JWT_ALGORITHM,
    )
    resp = client.get("/expenses", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401


def test_protected_route_rejects_token_signed_with_other_secret(client, auth):
    forged = jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        "a-different-secret-also-32-bytes-long", algorithm=JWT_ALGORITHM,
    )
    resp = client.get("/expenses", headers={"Authorization": f"Bearer {forged}"})
    assert resp.status_code == 401


def test_protected_route_rejects_token_for_deleted_user(client):
    token = create_access_token(9999)
    resp = client.get("/expenses", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
