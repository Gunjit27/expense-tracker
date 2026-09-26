import pytest


def test_create_expense(add_expense, categories):
    exp = add_expense(amount="249.50", category="Transport", payment_method="Card",
                      expense_date="2026-09-10", description="Cab")
    assert float(exp["amount"]) == 249.50
    assert exp["category_id"] == categories["Transport"]
    assert exp["payment_method"] == "Card"
    assert exp["expense_date"] == "2026-09-10"
    assert exp["description"] == "Cab"
    assert exp["id"] and exp["created_at"]


def test_create_expense_with_unknown_category(client, auth):
    resp = client.post("/expenses", headers=auth, json={
        "amount": "10", "category_id": 9999, "payment_method": "UPI", "expense_date": "2026-09-01",
    })
    assert resp.status_code == 400


def test_create_expense_with_other_users_category(client, auth, other_auth, categories):
    resp = client.post("/expenses", headers=other_auth, json={
        "amount": "10", "category_id": categories["Food"], "payment_method": "UPI",
        "expense_date": "2026-09-01",
    })
    assert resp.status_code == 400


@pytest.mark.parametrize("amount", ["0", "-5", "1.234", "12345678901.00"])
def test_create_expense_rejects_invalid_amount(client, auth, categories, amount):
    resp = client.post("/expenses", headers=auth, json={
        "amount": amount, "category_id": categories["Food"], "payment_method": "UPI",
        "expense_date": "2026-09-01",
    })
    assert resp.status_code == 422


def test_list_expenses_ordered_newest_first(client, auth, add_expense):
    add_expense(expense_date="2026-08-01", description="old")
    add_expense(expense_date="2026-09-15", description="new")
    add_expense(expense_date="2026-09-01", description="mid")
    rows = client.get("/expenses", headers=auth).json()
    assert [r["description"] for r in rows] == ["new", "mid", "old"]
    assert rows[0]["category_name"] == "Food"


def test_list_expenses_filters(client, auth, categories, add_expense):
    add_expense(category="Food", payment_method="UPI", expense_date="2026-07-10")
    add_expense(category="Food", payment_method="Cash", expense_date="2026-08-10")
    add_expense(category="Bills", payment_method="UPI", expense_date="2026-09-10")

    def count(**params):
        return len(client.get("/expenses", headers=auth, params=params).json())

    assert count() == 3
    assert count(category_id=categories["Food"]) == 2
    assert count(payment_method="UPI") == 2
    assert count(start_date="2026-08-01") == 2
    assert count(end_date="2026-08-10") == 2
    assert count(start_date="2026-08-01", end_date="2026-08-31") == 1
    assert count(category_id=categories["Food"], payment_method="UPI") == 1


def test_list_expenses_only_returns_own(client, auth, other_auth, add_expense):
    add_expense()
    assert client.get("/expenses", headers=other_auth).json() == []


def test_update_expense(client, auth, categories, add_expense):
    exp = add_expense(amount="50")
    resp = client.put(f"/expenses/{exp['id']}", headers=auth, json={
        "amount": "75.25", "category_id": categories["Shopping"], "payment_method": "Card",
        "expense_date": "2026-09-20", "description": "Shoes",
    })
    assert resp.status_code == 200
    row = client.get("/expenses", headers=auth).json()[0]
    assert float(row["amount"]) == 75.25
    assert row["category_name"] == "Shopping"
    assert row["description"] == "Shoes"


def test_update_expense_invalid_category(client, auth, add_expense):
    exp = add_expense()
    resp = client.put(f"/expenses/{exp['id']}", headers=auth, json={
        "amount": "1", "category_id": 9999, "payment_method": "UPI", "expense_date": "2026-09-01",
    })
    assert resp.status_code == 400


def test_update_other_users_expense(client, other_auth, add_expense):
    exp = add_expense()
    other_cats = {c["name"]: c["id"] for c in client.get("/categories", headers=other_auth).json()}
    resp = client.put(f"/expenses/{exp['id']}", headers=other_auth, json={
        "amount": "1", "category_id": other_cats["Food"], "payment_method": "UPI",
        "expense_date": "2026-09-01",
    })
    assert resp.status_code == 404


def test_delete_expense(client, auth, add_expense):
    exp = add_expense()
    assert client.delete(f"/expenses/{exp['id']}", headers=auth).status_code == 200
    assert client.get("/expenses", headers=auth).json() == []
    assert client.delete(f"/expenses/{exp['id']}", headers=auth).status_code == 404


def test_delete_other_users_expense(client, auth, other_auth, add_expense):
    exp = add_expense()
    assert client.delete(f"/expenses/{exp['id']}", headers=other_auth).status_code == 404
    assert len(client.get("/expenses", headers=auth).json()) == 1
