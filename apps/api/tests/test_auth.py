import uuid


def _email():
    return f"u-{uuid.uuid4().hex[:8]}@test.local"


def test_register_login_me_logout(client):
    email = _email()
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "a-long-password"})
    assert r.status_code == 201

    r = client.get("/api/v1/auth/me")
    assert r.status_code == 200 and r.json()["email"] == email

    r = client.post("/api/v1/auth/logout")
    assert r.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401

    r = client.post("/api/v1/auth/login", json={"email": email, "password": "a-long-password"})
    assert r.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 200


def test_weak_password_rejected(client):
    r = client.post("/api/v1/auth/register", json={"email": _email(), "password": "short"})
    assert r.status_code == 400


def test_wrong_password_generic_401(client):
    email = _email()
    client.post("/api/v1/auth/register", json={"email": email, "password": "a-long-password"})
    client.post("/api/v1/auth/logout")
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "wrong-password!"})
    assert r.status_code == 401
    assert "password" in r.json()["detail"]  # generic message, no user enumeration


def test_duplicate_email_conflict(client):
    email = _email()
    assert client.post("/api/v1/auth/register", json={"email": email, "password": "a-long-password"}).status_code == 201
    client.post("/api/v1/auth/logout")
    assert client.post("/api/v1/auth/register", json={"email": email, "password": "a-long-password"}).status_code == 409


def test_protected_routes_require_auth(client):
    client.post("/api/v1/auth/logout")
    assert client.get("/api/v1/connected-accounts").status_code == 401
    assert client.get("/api/v1/posts").status_code == 401
