from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import (ConnectedAccount, DraftMedia, MediaAsset, PostDraft,
                      PostTarget, PublishJob, Workspace, utcnow)
from ..security.ratelimit import rate_limit
from ..security.sessions import current_user, current_workspace
from ..services.audit import write_audit
from ..services.captions import SUPPORTED_PLATFORMS, generate_captions, validate_target
from ..services.state_machine import IllegalTransition, transition

router = APIRouter(prefix="/posts", tags=["posts"])


class CreateDraft(BaseModel):
    master_caption: str = ""
    media_asset_ids: list[str] = []        # photos, in display order (max 20)
    video_asset_id: str | None = None      # single video
    platforms: list[str]


class PatchTarget(BaseModel):
    caption: str | None = None
    title: str | None = None
    privacy: str | None = None
    scheduled_at: datetime | None = None      # UTC ISO from frontend
    timezone_name: str | None = None


class PublishBody(BaseModel):
    target_ids: list[str] | None = None
    schedule_at: datetime | None = None       # UTC; None => publish now
    timezone_name: str = "UTC"


def _owned_draft(draft_id: str, ws: Workspace, db: Session) -> PostDraft:
    d = db.get(PostDraft, draft_id)
    if d is None or d.workspace_id != ws.id:
        raise HTTPException(404, "post not found")
    return d


def _media_info(draft: PostDraft, db: Session) -> tuple[int, bool, list[dict]]:
    """Returns (photo_count, has_video, media list for API output)."""
    rows = (db.query(DraftMedia, MediaAsset)
              .join(MediaAsset, DraftMedia.media_asset_id == MediaAsset.id)
              .filter(DraftMedia.post_draft_id == draft.id)
              .order_by(DraftMedia.position).all())
    photos = sum(1 for dm, _ in rows if dm.kind == "photo")
    has_video = any(dm.kind == "video" for dm, _ in rows)
    out = [{"id": a.id, "kind": dm.kind, "mime_type": a.mime_type,
            "original_name": a.original_name} for dm, a in rows]
    return photos, has_video, out


def _target_out(t: PostTarget, db: Session) -> dict:
    job = (db.query(PublishJob).filter(PublishJob.post_target_id == t.id)
             .order_by(PublishJob.created_at.desc()).first())
    return {
        "id": t.id, "platform": t.platform, "status": t.status,
        "caption": t.caption, "title": t.title, "privacy": t.privacy,
        "scheduled_at": t.scheduled_at.isoformat() + "Z" if t.scheduled_at else None,
        "timezone_name": t.timezone_name,
        "validation_errors": t.validation_errors or [],
        "connected_account_id": t.connected_account_id,
        "job": {"state": job.state, "attempts": job.attempts, "error": job.last_error,
                "external_url": job.external_url, "external_post_id": job.external_post_id} if job else None,
    }


def _draft_out(d: PostDraft, db: Session) -> dict:
    targets = db.query(PostTarget).filter(PostTarget.post_draft_id == d.id).all()
    _, _, media = _media_info(d, db)
    return {"id": d.id, "master_caption": d.master_caption, "media": media,
            "created_at": d.created_at.isoformat() + "Z",
            "targets": [_target_out(t, db) for t in targets]}


@router.post("", status_code=201)
def create_draft(body: CreateDraft, ws: Workspace = Depends(current_workspace),
                 user=Depends(current_user), db: Session = Depends(get_db)):
    bad = [p for p in body.platforms if p not in SUPPORTED_PLATFORMS]
    if bad:
        raise HTTPException(400, f"unsupported platforms: {bad}")
    if not body.platforms:
        raise HTTPException(400, "select at least one platform")
    if len(body.media_asset_ids) > 20:
        raise HTTPException(400, "maximum 20 photos per post")

    # ownership + kind checks on every referenced asset
    photo_assets: list[MediaAsset] = []
    for aid in body.media_asset_ids:
        m = db.get(MediaAsset, aid)
        if m is None or m.workspace_id != ws.id:
            raise HTTPException(404, "media not found")
        if not m.mime_type.startswith("image/"):
            raise HTTPException(400, f"{m.original_name} is not an image — use the video slot for videos")
        photo_assets.append(m)
    video_asset = None
    if body.video_asset_id:
        video_asset = db.get(MediaAsset, body.video_asset_id)
        if video_asset is None or video_asset.workspace_id != ws.id:
            raise HTTPException(404, "video not found")
        if not video_asset.mime_type.startswith("video/"):
            raise HTTPException(400, "video slot only accepts MP4 files")

    draft = PostDraft(workspace_id=ws.id, created_by=user.id,
                      master_caption=body.master_caption)
    db.add(draft); db.flush()
    for i, m in enumerate(photo_assets):
        db.add(DraftMedia(post_draft_id=draft.id, media_asset_id=m.id, kind="photo", position=i))
    if video_asset is not None:
        db.add(DraftMedia(post_draft_id=draft.id, media_asset_id=video_asset.id,
                          kind="video", position=len(photo_assets)))
    db.flush()

    captions = generate_captions(body.master_caption, body.platforms)
    photo_count, has_video, _ = _media_info(draft, db)
    for p in body.platforms:
        account = (db.query(ConnectedAccount)
                     .filter(ConnectedAccount.workspace_id == ws.id,
                             ConnectedAccount.platform == p,
                             ConnectedAccount.status == "active").first())
        t = PostTarget(post_draft_id=draft.id, platform=p,
                       connected_account_id=account.id if account else None,
                       caption=captions[p]["caption"], title=captions[p]["title"])
        t.validation_errors = validate_target(p, t.caption, t.title, photo_count, has_video)
        db.add(t)
    write_audit(db, action="draft_created", workspace_id=ws.id, actor_user_id=user.id,
                entity_type="post_draft", entity_id=draft.id)
    db.commit()
    return _draft_out(draft, db)


@router.get("")
def list_posts(platform: str | None = None, status: str | None = None,
               ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    q = (db.query(PostTarget).join(PostDraft, PostTarget.post_draft_id == PostDraft.id)
           .filter(PostDraft.workspace_id == ws.id))
    if platform:
        q = q.filter(PostTarget.platform == platform)
    if status:
        q = q.filter(PostTarget.status == status)
    targets = q.order_by(PostTarget.updated_at.desc()).limit(200).all()
    return [{**_target_out(t, db), "post_draft_id": t.post_draft_id,
             "master_caption": t.draft.master_caption} for t in targets]


@router.get("/{draft_id}")
def get_draft(draft_id: str, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    return _draft_out(_owned_draft(draft_id, ws, db), db)


@router.get("/{draft_id}/status")
def draft_status(draft_id: str, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    d = _owned_draft(draft_id, ws, db)
    return {"id": d.id, "targets": [_target_out(t, db) for t in
                                    db.query(PostTarget).filter(PostTarget.post_draft_id == d.id).all()]}


@router.patch("/targets/{target_id}")
def patch_target(target_id: str, body: PatchTarget,
                 ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    t = db.get(PostTarget, target_id)
    if t is None:
        raise HTTPException(404, "target not found")
    d = _owned_draft(t.post_draft_id, ws, db)
    if t.status not in ("draft", "scheduled", "failed"):
        raise HTTPException(409, f"cannot edit target in state {t.status}")
    if body.caption is not None: t.caption = body.caption
    if body.title is not None: t.title = body.title
    if body.privacy is not None: t.privacy = body.privacy
    if body.scheduled_at is not None: t.scheduled_at = body.scheduled_at.replace(tzinfo=None)
    if body.timezone_name is not None: t.timezone_name = body.timezone_name
    pc, hv, _ = _media_info(d, db)
    t.validation_errors = validate_target(t.platform, t.caption, t.title, pc, hv)
    db.commit()
    return _target_out(t, db)


@router.post("/{draft_id}/publish", status_code=202)
def publish(draft_id: str, body: PublishBody,
            idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=80),
            ws: Workspace = Depends(current_workspace), user=Depends(current_user),
            db: Session = Depends(get_db),
            _rl=Depends(rate_limit("publish", get_settings().publish_rate_per_min, 60))):
    d = _owned_draft(draft_id, ws, db)
    targets = db.query(PostTarget).filter(PostTarget.post_draft_id == d.id).all()
    if body.target_ids is not None:
        targets = [t for t in targets if t.id in set(body.target_ids)]
    if not targets:
        raise HTTPException(400, "no targets to publish")

    # server-side re-validation — never trust the client
    photo_count, has_video, _ = _media_info(d, db)
    blocked = []
    for t in targets:
        errs = validate_target(t.platform, t.caption, t.title, photo_count, has_video)
        s = get_settings()
        real_enabled = {"linkedin": s.enable_linkedin_real, "facebook": s.enable_facebook_real,
                        "twitter": s.enable_twitter_real,
                        "youtube": s.enable_youtube_real}.get(t.platform, False)
        if real_enabled and not t.connected_account_id:
            errs.append(f"no {t.platform} account connected")
        t.validation_errors = errs
        if errs:
            blocked.append({"target_id": t.id, "platform": t.platform, "errors": errs})
    if blocked:
        db.commit()
        raise HTTPException(422, {"message": "validation failed", "blocked": blocked})

    results = []
    for t in targets:
        # Idempotency FIRST: the same Idempotency-Key must return the same job,
        # regardless of what state the first request moved the target into.
        key = f"{idempotency_key}:{t.id}"
        existing = db.query(PublishJob).filter(PublishJob.idempotency_key == key).first()
        if existing:
            results.append({"target_id": t.id, "job_id": existing.id, "duplicate": True})
            continue
        if t.status not in ("draft", "scheduled", "failed"):
            results.append({"target_id": t.id, "skipped": f"state {t.status}"})
            continue
        if body.schedule_at is not None:
            t.scheduled_at = body.schedule_at.replace(tzinfo=None)
            t.timezone_name = body.timezone_name
            if t.status != "scheduled":
                transition(t, "scheduled")
            results.append({"target_id": t.id, "scheduled_for": t.scheduled_at.isoformat() + "Z"})
            continue
        job = PublishJob(post_target_id=t.id, idempotency_key=key,
                         max_attempts=get_settings().job_max_attempts)
        db.add(job)
        try:
            transition(t, "queued")
        except IllegalTransition as e:
            raise HTTPException(409, str(e))
        db.flush()
        results.append({"target_id": t.id, "job_id": job.id})
    write_audit(db, action="publish_requested", workspace_id=ws.id, actor_user_id=user.id,
                entity_type="post_draft", entity_id=d.id,
                meta={"idempotency_key": idempotency_key,
                      "scheduled": body.schedule_at.isoformat() if body.schedule_at else None})
    db.commit()
    return {"results": results}


@router.post("/jobs/{job_id}/retry", status_code=202)
def retry_job(job_id: str, ws: Workspace = Depends(current_workspace),
              user=Depends(current_user), db: Session = Depends(get_db)):
    job = db.get(PublishJob, job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    t = db.get(PostTarget, job.post_target_id)
    _owned_draft(t.post_draft_id, ws, db)
    if job.state != "failed_final" or t.status not in ("failed", "requires_action"):
        raise HTTPException(409, "only finally-failed jobs can be retried")
    new_job = PublishJob(post_target_id=t.id, idempotency_key=f"retry:{job.id}:{utcnow().timestamp():.0f}",
                         max_attempts=get_settings().job_max_attempts)
    db.add(new_job)
    transition(t, "queued")
    write_audit(db, action="job_retried", workspace_id=ws.id, actor_user_id=user.id,
                entity_type="publish_job", entity_id=job.id, platform=t.platform)
    db.commit()
    return {"job_id": new_job.id}
