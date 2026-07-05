"""Real LinkedIn publisher — official Posts API (versioned REST).

Flow: (image? initializeUpload -> PUT bytes -> image URN) -> POST /rest/posts.
Headers required by LinkedIn: LinkedIn-Version (YYYYMM) + X-Restli-Protocol-Version.
Tokens are decrypted only here, at call time, and never logged.
"""
import logging

import httpx
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import ConnectedAccount, MediaAsset, PostTarget, utcnow
from ..security.crypto import TokenCryptoError, decrypt_token
from ..services.media import read_media_bytes
from .base import PublishResult

log = logging.getLogger("publishers.linkedin")

API = "https://api.linkedin.com"
# LinkedIn "little text" reserved characters (keep # and @ usable for tags/mentions)
_ESCAPE_CHARS = "\\(){}<>[]*_~|"


def escape_commentary(text: str) -> str:
    out = []
    for ch in text or "":
        if ch in _ESCAPE_CHARS:
            out.append("\\" + ch)
        else:
            out.append(ch)
    return "".join(out)


class LinkedInPublisher:
    platform = "linkedin"

    def _headers(self, token: str) -> dict:
        s = get_settings()
        return {
            "Authorization": f"Bearer {token}",
            "LinkedIn-Version": s.linkedin_api_version,
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }

    def publish(self, db: Session, target: PostTarget,
                account: ConnectedAccount | None,
                media_list: list[MediaAsset]) -> PublishResult:
        if account is None or account.status != "active":
            return PublishResult(ok=False, retryable=False,
                                 error="LinkedIn account not connected (or revoked) — reconnect in Settings")
        if account.token_expires_at and account.token_expires_at <= utcnow():
            account.status = "expired"
            return PublishResult(ok=False, retryable=False,
                                 error="LinkedIn token expired — reconnect in Settings")
        try:
            token = decrypt_token(account.enc_access_token, account.key_version)
        except TokenCryptoError as e:
            return PublishResult(ok=False, retryable=False, error=f"token decryption failed: {e}")

        images = [m for m in media_list if m.mime_type in ("image/jpeg", "image/png")]
        videos = [m for m in media_list if m.mime_type.startswith("video/")]
        if videos:
            return PublishResult(ok=False, retryable=False,
                                 error="LinkedIn video upload is coming soon — post photos or text for now")
        if len(images) > 20:
            return PublishResult(ok=False, retryable=False,
                                 error="LinkedIn supports at most 20 images per post")

        author = account.external_account_id  # urn:li:person:...
        try:
            with httpx.Client(timeout=120) as client:
                image_urns: list[str] = []
                for img in images:
                    urn, err = self._upload_image(client, token, author, img)
                    if err:
                        return err
                    image_urns.append(urn)

                body: dict = {
                    "author": author,
                    "commentary": escape_commentary(target.caption or ""),
                    "visibility": "PUBLIC",
                    "distribution": {
                        "feedDistribution": "MAIN_FEED",
                        "targetEntities": [],
                        "thirdPartyDistributionChannels": [],
                    },
                    "lifecycleState": "PUBLISHED",
                    "isReshareDisabledByAuthor": False,
                }
                if len(image_urns) == 1:
                    body["content"] = {"media": {"id": image_urns[0],
                                                 "title": (target.title or images[0].original_name or "image")[:100]}}
                elif len(image_urns) > 1:
                    body["content"] = {"multiImage": {"images": [
                        {"id": urn, "altText": (images[i].original_name or f"image {i+1}")[:120]}
                        for i, urn in enumerate(image_urns)
                    ]}}

                r = client.post(f"{API}/rest/posts", json=body, headers=self._headers(token))
        except httpx.HTTPError as e:
            return PublishResult(ok=False, retryable=True, error=f"network error: {type(e).__name__}")

        if r.status_code == 201:
            post_urn = r.headers.get("x-restli-id", "")
            return PublishResult(
                ok=True, external_post_id=post_urn,
                external_url=f"https://www.linkedin.com/feed/update/{post_urn}/" if post_urn else None,
                raw={"status": r.status_code, "restli_id": post_urn},
            )
        return self._classify_failure(r, account)

    def _upload_image(self, client: httpx.Client, token: str, author: str,
                      media: MediaAsset) -> tuple[str | None, PublishResult | None]:
        init = client.post(
            f"{API}/rest/images?action=initializeUpload",
            json={"initializeUploadRequest": {"owner": author}},
            headers=self._headers(token),
        )
        if init.status_code != 200:
            return None, self._classify_failure(init, None, context="image initializeUpload")
        value = init.json().get("value", {})
        upload_url, image_urn = value.get("uploadUrl"), value.get("image")
        if not upload_url or not image_urn:
            return None, PublishResult(ok=False, retryable=True, error="initializeUpload returned no uploadUrl",
                                       raw={"status": init.status_code})
        up = client.put(upload_url, content=read_media_bytes(media),
                        headers={"Authorization": f"Bearer {token}",
                                 "Content-Type": "application/octet-stream"})
        if up.status_code not in (200, 201):
            return None, PublishResult(ok=False, retryable=up.status_code >= 500 or up.status_code == 429,
                                       error=f"image upload failed (HTTP {up.status_code})",
                                       raw={"status": up.status_code})
        return image_urn, None

    def _classify_failure(self, r: httpx.Response, account: ConnectedAccount | None,
                          context: str = "post") -> PublishResult:
        try:
            detail = r.json().get("message", "")[:300]
        except Exception:
            detail = r.text[:300]
        if r.status_code in (401, 403):
            if account is not None:
                account.status = "revoked"  # token invalid/revoked — force reconnect
            return PublishResult(ok=False, retryable=False,
                                 error=f"LinkedIn auth failed ({r.status_code}) on {context}: {detail} — reconnect in Settings",
                                 raw={"status": r.status_code, "body": detail})
        retryable = r.status_code == 429 or r.status_code >= 500
        return PublishResult(ok=False, retryable=retryable,
                             error=f"LinkedIn {context} failed (HTTP {r.status_code}): {detail}",
                             raw={"status": r.status_code, "body": detail})
