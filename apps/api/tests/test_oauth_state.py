def test_callback_rejects_forged_state(auth_client):
    r = auth_client.get("/api/v1/oauth/linkedin/callback",
                        params={"code": "fake-code", "state": "forged-state-value"})
    assert r.status_code == 400  # CSRF protection


def test_start_requires_configuration(auth_client):
    # test env has no LinkedIn credentials — endpoint must fail loudly, not silently
    r = auth_client.post("/api/v1/oauth/linkedin/start")
    assert r.status_code == 500
    assert "not configured" in r.json()["detail"]


def test_config_endpoint_exposes_no_secrets(auth_client):
    r = auth_client.get("/api/v1/oauth/linkedin/config")
    assert r.status_code == 200
    body = r.json()
    assert body["redirect_uri"].endswith("/api/v1/oauth/linkedin/callback")
    assert body["client_id_configured"] is False   # test env has no creds
    assert body["secret_configured"] is False
    assert "client_secret" not in str(body).lower()  # never leak the actual secret


def test_callback_requires_login(client):
    client.post("/api/v1/auth/logout")
    r = client.get("/api/v1/oauth/linkedin/callback", params={"code": "x", "state": "y"})
    assert r.status_code == 401
