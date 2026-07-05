import httpx
import respx

from app.routers.github import _excluded


def test_upload_filters_block_secrets_and_junk():
    assert _excluded(".env") == "secret file (.env*)"
    assert _excluded("apps/api/.env.local") == "secret file (.env*)"
    assert _excluded("node_modules/react/index.js") == "inside node_modules/"
    assert _excluded("apps/web/.next/build.js") == "inside .next/"
    assert _excluded("app/__pycache__/x.pyc") is not None
    assert _excluded("../../etc/passwd") == "path traversal"
    assert _excluded("app.log") == "generated/temporary file"
    assert _excluded("data/app.db") == "inside data/"
    # legitimate files pass
    assert _excluded("apps/api/app/main.py") is None
    assert _excluded("README.md") is None
    assert _excluded("apps/web/package.json") is None


@respx.mock
def test_token_rejected_when_github_says_no(auth_client):
    respx.get("https://api.github.com/user").mock(return_value=httpx.Response(401))
    r = auth_client.post("/api/v1/github/token", json={"token": "ghp_" + "x" * 30})
    assert r.status_code == 400


@respx.mock
def test_token_saved_encrypted_and_upload_requires_it(auth_client):
    # upload before connecting -> clear error
    r = auth_client.post("/api/v1/github/upload",
                         data={"repo": "demo", "paths": "[]"}, files=[])
    assert r.status_code in (400, 422)

    respx.get("https://api.github.com/user").mock(
        return_value=httpx.Response(200, json={"login": "tester", "name": "Test Er"}))
    r = auth_client.post("/api/v1/github/token", json={"token": "ghp_" + "y" * 36})
    assert r.status_code == 200 and r.json()["login"] == "tester"

    # token is stored encrypted — the raw value must not appear in the accounts API
    accounts = auth_client.get("/api/v1/connected-accounts").json()
    gh = [a for a in accounts if a["platform"] == "github"][0]
    assert gh["status"] == "active"
    assert "ghp_" not in str(accounts)
