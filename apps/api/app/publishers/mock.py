"""Mock/demo publisher for platforms not yet integrated (GitHub/YouTube today).

Demo hooks: include "[fail]" in a caption to simulate a permanent failure,
"[flaky]" to simulate a retryable failure on the first attempts.
"""
import time
import uuid

from sqlalchemy.orm import Session

from ..models import ConnectedAccount, MediaAsset, PostTarget
from .base import PublishResult

_DEMO_URLS = {
    "github": "https://github.com/demo/social-poster/discussions/{id}",
    "youtube": "https://youtube.com/watch?v={id}",
}


class MockPublisher:
    def __init__(self, platform: str):
        self.platform = platform

    def publish(self, db: Session, target: PostTarget,
                account: ConnectedAccount | None,
                media_list: list[MediaAsset]) -> PublishResult:
        time.sleep(0.5)  # feel like a network call
        cap = target.caption or ""
        if "[fail]" in cap:
            return PublishResult(ok=False, retryable=False,
                                 error=f"{self.platform} demo: permanent validation failure",
                                 raw={"mock": True})
        if "[flaky]" in cap:
            return PublishResult(ok=False, retryable=True,
                                 error=f"{self.platform} demo: transient 503",
                                 raw={"mock": True})
        fake_id = uuid.uuid4().hex[:10]
        url_tpl = _DEMO_URLS.get(self.platform, "https://example.com/{platform}/{id}")
        return PublishResult(
            ok=True, external_post_id=f"mock-{self.platform}-{fake_id}",
            external_url=url_tpl.format(platform=self.platform, id=fake_id),
            raw={"mock": True, "platform": self.platform,
                 "media_count": len(media_list)},
        )
