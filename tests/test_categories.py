def test_create_category(client, auth):
    resp = client.post("/categories", headers=auth, json={"name": "  Travel  "})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Travel"
    names = [c["name"] for c in client.get("/categories", headers=auth).json()]
    assert "Travel" in names
    assert names == sorted(names)


def test_create_duplicate_category(client, auth):
    resp = client.post("/categories", headers=auth, json={"name": "Food"})
    assert resp.status_code == 409


def test_create_category_rejects_empty_name(client, auth):
    assert client.post("/categories", headers=auth, json={"name": ""}).status_code == 422


def test_same_category_name_allowed_for_different_users(client, auth, other_auth):
    assert client.post("/categories", headers=auth, json={"name": "Gym"}).status_code == 200
    assert client.post("/categories", headers=other_auth, json={"name": "Gym"}).status_code == 200


def test_categories_are_per_user(client, auth, other_auth):
    client.post("/categories", headers=auth, json={"name": "Private"})
    other_names = [c["name"] for c in client.get("/categories", headers=other_auth).json()]
    assert "Private" not in other_names


def test_delete_category(client, auth):
    cat_id = client.post("/categories", headers=auth, json={"name": "Temp"}).json()["id"]
    assert client.delete(f"/categories/{cat_id}", headers=auth).status_code == 200
    ids = [c["id"] for c in client.get("/categories", headers=auth).json()]
    assert cat_id not in ids


def test_delete_missing_category(client, auth):
    assert client.delete("/categories/9999", headers=auth).status_code == 404


def test_cannot_delete_category_with_expenses(client, auth, categories, add_expense):
    add_expense(category="Food")
    resp = client.delete(f"/categories/{categories['Food']}", headers=auth)
    assert resp.status_code == 400


def test_cannot_delete_other_users_category(client, auth, other_auth, categories):
    resp = client.delete(f"/categories/{categories['Food']}", headers=other_auth)
    assert resp.status_code == 404
    assert "Food" in [c["name"] for c in client.get("/categories", headers=auth).json()]
