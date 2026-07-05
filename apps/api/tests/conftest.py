import os
import sys
import tempfile
import uuid

# Test env MUST be set before the app is imported (settings are cached).
_tmp = tempfile.mkdtemp(prefix="spa-test-")
os.environ.update({
    "APP_ENV": "dev",
    "RUN_WORKER": "false",
    "DATABASE_URL": f"sqlite:///{_tmp}/test.db",
    "STORAGE_DIR": f"{_tmp}/storage",
    "SESSION_SECRET": "test-session-secret-not-for-prod",
    "TOKEN_ENC_KEY_B64": "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",  # base64("0"*32)
    "TOKEN_ENC_KEY_VERSION": "1",
    "ENABLE_LINKEDIN_REAL": "false",
    "ENABLE_FACEBOOK_REAL": "false",
    "LINKEDIN_CLIENT_ID": "",
    "LINKEDIN_CLIENT_SECRET": "",
})

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient

from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    # per-IP limiter sees all tests as one client ("testclient") — isolate tests
    from app.security.ratelimit import _buckets
    _buckets.clear()
    yield


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_client(client):
    email = f"user-{uuid.uuid4().hex[:8]}@test.local"
    r = client.post("/api/v1/auth/register",
                    json={"email": email, "password": "sufficiently-long-pw"})
    assert r.status_code == 201, r.text
    client._test_email = email
    return client
