import uuid
from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, DateTime, ForeignKey, Integer, String, Text,
                        UniqueConstraint, Index)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    """Naive UTC — consistent across SQLite/Postgres for this app."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120))
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ConnectedAccount(Base):
    __tablename__ = "connected_accounts"
    __table_args__ = (UniqueConstraint("workspace_id", "platform", "external_account_id"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    platform: Mapped[str] = mapped_column(String(20))            # linkedin|facebook|instagram|youtube
    external_account_id: Mapped[str] = mapped_column(String(255))  # e.g. urn:li:person:xxx
    account_name: Mapped[str] = mapped_column(String(255), default="")
    enc_access_token: Mapped[str] = mapped_column(Text)          # base64(nonce||ciphertext)
    enc_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_version: Mapped[int] = mapped_column(Integer, default=1)
    scopes: Mapped[str] = mapped_column(String(500), default="")
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active|revoked|expired
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class MediaAsset(Base):
    __tablename__ = "media_assets"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    storage_key: Mapped[str] = mapped_column(String(500))
    original_name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))
    bytes: Mapped[int] = mapped_column(Integer)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str] = mapped_column(String(64))
    exif_stripped: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class DraftMedia(Base):
    """Draft ↔ media association: many photos and/or one video per draft."""
    __tablename__ = "draft_media"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    post_draft_id: Mapped[str] = mapped_column(ForeignKey("post_drafts.id"), index=True)
    media_asset_id: Mapped[str] = mapped_column(ForeignKey("media_assets.id"))
    kind: Mapped[str] = mapped_column(String(10))   # photo | video
    position: Mapped[int] = mapped_column(Integer, default=0)


class PostDraft(Base):
    __tablename__ = "post_drafts"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    master_caption: Mapped[str] = mapped_column(Text, default="")
    media_asset_id: Mapped[str | None] = mapped_column(ForeignKey("media_assets.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft|archived
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    targets: Mapped[list["PostTarget"]] = relationship(back_populates="draft")


class PostTarget(Base):
    __tablename__ = "post_targets"
    __table_args__ = (Index("ix_targets_status_sched", "status", "scheduled_at"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    post_draft_id: Mapped[str] = mapped_column(ForeignKey("post_drafts.id"), index=True)
    platform: Mapped[str] = mapped_column(String(20))
    connected_account_id: Mapped[str | None] = mapped_column(ForeignKey("connected_accounts.id"), nullable=True)
    caption: Mapped[str] = mapped_column(Text, default="")
    title: Mapped[str] = mapped_column(String(255), default="")     # youtube
    privacy: Mapped[str] = mapped_column(String(20), default="public")
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # UTC
    timezone_name: Mapped[str] = mapped_column(String(64), default="UTC")
    # draft|scheduled|queued|publishing|published|failed|requires_action|canceled
    status: Mapped[str] = mapped_column(String(20), default="draft")
    validation_errors: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    draft: Mapped["PostDraft"] = relationship(back_populates="targets")


class PublishJob(Base):
    __tablename__ = "publish_jobs"
    __table_args__ = (UniqueConstraint("idempotency_key"),
                      Index("ix_jobs_state_next", "state", "next_attempt_at"))
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    post_target_id: Mapped[str] = mapped_column(ForeignKey("post_targets.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    # queued|running|succeeded|failed_retryable|failed_final
    state: Mapped[str] = mapped_column(String(20), default="queued")
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_post_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    api_response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    workspace_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    actor_user_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(40), default="")
    entity_id: Mapped[str] = mapped_column(String(64), default="")
    platform: Mapped[str] = mapped_column(String(20), default="")
    ip: Mapped[str] = mapped_column(String(64), default="")
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class OAuthState(Base):
    __tablename__ = "oauth_states"
    state: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    provider: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
