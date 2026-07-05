"""In-process job worker + scheduler (dev mode).

Same responsibilities as the production Celery workers (see docs/02): dispatch due
scheduled targets, execute publish jobs with retry/backoff, watch token expiry.
Swapping to Celery later = move these three functions behind tasks; models unchanged.
"""
import logging
import random
from datetime import timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from ..config import get_settings
from ..db import SessionLocal
from ..models import (ConnectedAccount, DraftMedia, MediaAsset, Notification,
                      PostDraft, PostTarget, PublishJob, utcnow)
from ..publishers.base import get_publisher
from ..services.audit import notify, write_audit
from ..services.state_machine import transition

log = logging.getLogger("worker")
_scheduler: BackgroundScheduler | None = None


def dispatch_due_scheduled() -> int:
    """scheduled targets whose time has come -> queued + job created."""
    n = 0
    with SessionLocal() as db:
        due = (db.query(PostTarget)
                 .filter(PostTarget.status == "scheduled",
                         PostTarget.scheduled_at.isnot(None),
                         PostTarget.scheduled_at <= utcnow())
                 .limit(100).all())
        for t in due:
            key = f"sched:{t.id}:{t.scheduled_at.isoformat()}"
            exists = db.query(PublishJob).filter(PublishJob.idempotency_key == key).first()
            if exists is None:
                db.add(PublishJob(post_target_id=t.id, idempotency_key=key,
                                  max_attempts=get_settings().job_max_attempts))
            transition(t, "queued")
            n += 1
        db.commit()
    return n


def process_due_jobs(limit: int = 10) -> int:
    with SessionLocal() as db:
        rows = (db.query(PublishJob.id)
                  .filter(PublishJob.state.in_(("queued", "failed_retryable")),
                          PublishJob.next_attempt_at <= utcnow())
                  .order_by(PublishJob.next_attempt_at)
                  .limit(limit).all())
        ids = [r[0] for r in rows]
    for job_id in ids:
        try:
            run_job(job_id)
        except Exception:
            log.exception("job %s crashed", job_id)
    return len(ids)


def run_job(job_id: str) -> None:
    s = get_settings()
    # --- claim phase ---
    with SessionLocal() as db:
        job = db.get(PublishJob, job_id)
        if job is None or job.state not in ("queued", "failed_retryable"):
            return
        target = db.get(PostTarget, job.post_target_id)
        if target is None:
            job.state = "failed_final"; job.last_error = "target missing"; db.commit(); return
        if job.external_post_id:              # idempotency: previous attempt actually succeeded
            job.state = "succeeded"
            if target.status != "published":
                transition(target, "published")
            db.commit(); return
        if target.status == "queued":
            transition(target, "publishing")
        elif target.status != "publishing":   # canceled/requires_action meanwhile
            job.state = "failed_final"; job.last_error = f"target in state {target.status}"
            db.commit(); return
        job.state = "running"
        job.attempts += 1
        attempts = job.attempts
        db.commit()

        account = db.get(ConnectedAccount, target.connected_account_id) if target.connected_account_id else None
        draft = db.get(PostDraft, target.post_draft_id)
        media_list: list[MediaAsset] = []
        if draft:
            rows = (db.query(DraftMedia, MediaAsset)
                      .join(MediaAsset, DraftMedia.media_asset_id == MediaAsset.id)
                      .filter(DraftMedia.post_draft_id == draft.id)
                      .order_by(DraftMedia.position).all())
            media_list = [a for _, a in rows]
        platform, target_id = target.platform, target.id
        owner_user_id = draft.created_by if draft else None
        workspace_id = draft.workspace_id if draft else None

        # --- network phase (no open transaction) ---
        publisher = get_publisher(platform)
        result = publisher.publish(db, target, account, media_list)
        db.commit()  # persist any account status change made by the publisher (revoked/expired)

    # --- finalize phase ---
    with SessionLocal() as db:
        job = db.get(PublishJob, job_id)
        target = db.get(PostTarget, target_id)
        if result.ok:
            job.state = "succeeded"
            job.external_post_id = result.external_post_id
            job.external_url = result.external_url
            job.api_response = result.raw
            transition(target, "published")
            write_audit(db, action="publish_succeeded", workspace_id=workspace_id,
                        entity_type="post_target", entity_id=target_id, platform=platform,
                        meta={"external_post_id": result.external_post_id})
            if owner_user_id:
                notify(db, user_id=owner_user_id, type="publish_succeeded",
                       payload={"platform": platform, "url": result.external_url, "target_id": target_id})
        else:
            job.last_error = (result.error or "unknown error")[:2000]
            job.api_response = result.raw
            account_dead = "reconnect" in (result.error or "").lower()
            if result.retryable and attempts < job.max_attempts:
                backoff = s.job_base_backoff_s * (2 ** (attempts - 1))
                backoff = min(backoff, 900) + random.uniform(0, backoff * 0.2)
                job.state = "failed_retryable"
                job.next_attempt_at = utcnow() + timedelta(seconds=backoff)
                # target stays "publishing" while retries continue
            else:
                job.state = "failed_final"
                transition(target, "requires_action" if account_dead else "failed")
                write_audit(db, action="publish_failed", workspace_id=workspace_id,
                            entity_type="post_target", entity_id=target_id, platform=platform,
                            meta={"error": job.last_error, "attempts": attempts})
                if owner_user_id:
                    notify(db, user_id=owner_user_id, type="publish_failed",
                           payload={"platform": platform, "error": job.last_error, "target_id": target_id})
        db.commit()


def scan_token_expiry() -> None:
    with SessionLocal() as db:
        soon = utcnow() + timedelta(days=7)
        accounts = (db.query(ConnectedAccount)
                      .filter(ConnectedAccount.status == "active",
                              ConnectedAccount.token_expires_at.isnot(None),
                              ConnectedAccount.token_expires_at <= soon).all())
        for a in accounts:
            ws_owner = db.query(PostDraft.created_by).filter(PostDraft.workspace_id == a.workspace_id).first()
            owner_id = ws_owner[0] if ws_owner else None
            if owner_id is None:
                from ..models import Workspace
                ws = db.get(Workspace, a.workspace_id)
                owner_id = ws.owner_user_id if ws else None
            if owner_id is None:
                continue
            dup = (db.query(Notification)
                     .filter(Notification.user_id == owner_id,
                             Notification.type == "token_expiring",
                             Notification.read_at.is_(None)).first())
            if dup is None:
                notify(db, user_id=owner_id, type="token_expiring",
                       payload={"platform": a.platform, "account": a.account_name,
                                "expires_at": a.token_expires_at.isoformat()})
        db.commit()


def start_worker() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    sch = BackgroundScheduler(daemon=True, job_defaults={"coalesce": True, "max_instances": 1})
    sch.add_job(dispatch_due_scheduled, "interval", seconds=20, id="dispatch")
    sch.add_job(process_due_jobs, "interval", seconds=5, id="process")
    sch.add_job(scan_token_expiry, "interval", hours=12, id="token_scan")
    sch.start()
    _scheduler = sch
    log.info("in-process worker started")
    return sch
