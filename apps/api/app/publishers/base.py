"""PlatformPublisher interface + registry. Adding a platform = one new adapter."""
from dataclasses import dataclass, field
from typing import Protocol

from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import ConnectedAccount, MediaAsset, PostTarget


@dataclass
class PublishResult:
    ok: bool
    external_post_id: str | None = None
    external_url: str | None = None
    retryable: bool = False           # only meaningful when ok=False
    error: str | None = None
    raw: dict = field(default_factory=dict)


class PlatformPublisher(Protocol):
    platform: str

    def publish(self, db: Session, target: PostTarget,
                account: ConnectedAccount | None,
                media_list: list[MediaAsset]) -> PublishResult: ...


def get_publisher(platform: str) -> "PlatformPublisher":
    from .linkedin import LinkedInPublisher
    from .mock import MockPublisher

    s = get_settings()
    real: dict[str, tuple[bool, type | None]] = {
        "linkedin": (s.enable_linkedin_real, LinkedInPublisher),
        "facebook": (s.enable_facebook_real, None),  # real adapter: next milestone
        "twitter": (s.enable_twitter_real, None),    # real adapter: next milestone
        "youtube": (s.enable_youtube_real, None),    # real adapter: next milestone
    }
    enabled, cls = real.get(platform, (False, None))
    if enabled and cls is not None:
        return cls()
    return MockPublisher(platform)
