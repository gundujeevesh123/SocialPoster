import json
from datetime import timedelta

import httpx
import respx

from app.db import SessionLocal
from app.models import (ConnectedAccount, MediaAsset, PostTarget, User,
                        Workspace, utcnow)
from app.publishers.linkedin import LinkedInPublisher, escape_commentary
from app.security.crypto import encrypt_token


def _account(db) -> ConnectedAccount:
    user = User(email=f"li-{utcnow().timestamp()}@t.local", password_hash="x")
    db.add(user); db.flush()
    ws = Workspace(name="w", owner_user_id=user.id)
    db.add(ws); db.flush()
    blob, ver = encrypt_token("fake-linkedin-token")
    acc = ConnectedAccount(workspace_id=ws.id, platform="linkedin",
                           external_account_id="urn:li:person:abc123",
                           enc_access_token=blob, key_version=ver,
                           token_expires_at=utcnow() + timedelta(days=30),
                           status="active")
    db.add(acc); db.flush()
    return acc


def test_escape_commentary():
    assert escape_commentary("hi (world) [x] *bold*") == r"hi \(world\) \[x\] \*bold\*"
    assert escape_commentary("#hashtag @mention stays") == "#hashtag @mention stays"


@respx.mock
def test_text_post_success(client):
    respx.post("https://api.linkedin.com/rest/posts").mock(
        return_value=httpx.Response(201, headers={"x-restli-id": "urn:li:share:777"}))
    with SessionLocal() as db:
        acc = _account(db)
        target = PostTarget(post_draft_id="x", platform="linkedin", caption="hello linkedin")
        res = LinkedInPublisher().publish(db, target, acc, [])
    assert res.ok
    assert res.external_post_id == "urn:li:share:777"
    assert "linkedin.com/feed/update" in res.external_url


@respx.mock
def test_versioned_headers_sent(client):
    route = respx.post("https://api.linkedin.com/rest/posts").mock(
        return_value=httpx.Response(201, headers={"x-restli-id": "urn:li:share:1"}))
    with SessionLocal() as db:
        acc = _account(db)
        LinkedInPublisher().publish(db, PostTarget(post_draft_id="x", platform="linkedin",
                                                   caption="hi"), acc, [])
    sent = route.calls.last.request.headers
    assert sent["X-Restli-Protocol-Version"] == "2.0.0"
    assert sent["LinkedIn-Version"]  # pinned YYYYMM
    assert sent["Authorization"].startswith("Bearer ")


@respx.mock
def test_429_is_retryable_and_401_marks_revoked(client):
    respx.post("https://api.linkedin.com/rest/posts").mock(
        return_value=httpx.Response(429, json={"message": "throttled"}))
    with SessionLocal() as db:
        acc = _account(db)
        res = LinkedInPublisher().publish(db, PostTarget(post_draft_id="x", platform="linkedin",
                                                         caption="hi"), acc, [])
        assert not res.ok and res.retryable

    respx.post("https://api.linkedin.com/rest/posts").mock(
        return_value=httpx.Response(401, json={"message": "expired"}))
    with SessionLocal() as db:
        acc = _account(db)
        res = LinkedInPublisher().publish(db, PostTarget(post_draft_id="x", platform="linkedin",
                                                         caption="hi"), acc, [])
        assert not res.ok and not res.retryable
        assert acc.status == "revoked"
        assert "reconnect" in res.error.lower()


@respx.mock
def test_multi_image_post_uses_multiimage(client, monkeypatch):
    import app.publishers.linkedin as li
    monkeypatch.setattr(li, "read_media_bytes", lambda a: b"fake-bytes")
    respx.post(url__startswith="https://api.linkedin.com/rest/images").mock(side_effect=[
        httpx.Response(200, json={"value": {"uploadUrl": "https://upload.linkedin.test/u1",
                                            "image": "urn:li:image:1"}}),
        httpx.Response(200, json={"value": {"uploadUrl": "https://upload.linkedin.test/u2",
                                            "image": "urn:li:image:2"}}),
    ])
    respx.put(url__startswith="https://upload.linkedin.test/").mock(
        return_value=httpx.Response(201))
    posts_route = respx.post("https://api.linkedin.com/rest/posts").mock(
        return_value=httpx.Response(201, headers={"x-restli-id": "urn:li:share:99"}))

    with SessionLocal() as db:
        acc = _account(db)
        m1 = MediaAsset(workspace_id=acc.workspace_id, storage_key="x/a.jpg", original_name="a.jpg",
                        mime_type="image/jpeg", bytes=10, sha256="0" * 64)
        m2 = MediaAsset(workspace_id=acc.workspace_id, storage_key="x/b.png", original_name="b.png",
                        mime_type="image/png", bytes=10, sha256="1" * 64)
        res = LinkedInPublisher().publish(
            db, PostTarget(post_draft_id="x", platform="linkedin", caption="two pics"), acc, [m1, m2])

    assert res.ok and res.external_post_id == "urn:li:share:99"
    body = json.loads(posts_route.calls.last.request.content)
    images = body["content"]["multiImage"]["images"]
    assert [i["id"] for i in images] == ["urn:li:image:1", "urn:li:image:2"]


@respx.mock
def test_video_rejected_for_now(client):
    with SessionLocal() as db:
        acc = _account(db)
        vid = MediaAsset(workspace_id=acc.workspace_id, storage_key="x/v.mp4", original_name="v.mp4",
                         mime_type="video/mp4", bytes=10, sha256="2" * 64)
        res = LinkedInPublisher().publish(
            db, PostTarget(post_draft_id="x", platform="linkedin", caption="vid"), acc, [vid])
    assert not res.ok and not res.retryable
    assert "coming soon" in res.error


def test_expired_token_short_circuits(client):
    with SessionLocal() as db:
        acc = _account(db)
        acc.token_expires_at = utcnow() - timedelta(days=1)
        res = LinkedInPublisher().publish(db, PostTarget(post_draft_id="x", platform="linkedin",
                                                         caption="hi"), acc, [])
    assert not res.ok and not res.retryable
    assert "expired" in res.error.lower()
