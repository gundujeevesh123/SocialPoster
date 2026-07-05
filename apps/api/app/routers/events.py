"""Server-Sent Events for live publish status (DB-poll based — fine for dev/single node)."""
import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..db import SessionLocal, get_db
from ..models import PostDraft, PostTarget, PublishJob, Workspace
from ..security.sessions import current_workspace

router = APIRouter(tags=["events"])

TERMINAL = {"published", "failed", "canceled", "requires_action"}


def _snapshot(draft_id: str) -> list[dict]:
    with SessionLocal() as db:
        targets = db.query(PostTarget).filter(PostTarget.post_draft_id == draft_id).all()
        out = []
        for t in targets:
            job = (db.query(PublishJob).filter(PublishJob.post_target_id == t.id)
                     .order_by(PublishJob.created_at.desc()).first())
            out.append({"target_id": t.id, "platform": t.platform, "status": t.status,
                        "attempts": job.attempts if job else 0,
                        "error": job.last_error if job else None,
                        "external_url": job.external_url if job else None})
        return out


@router.get("/posts/{draft_id}/events")
async def events(draft_id: str, ws: Workspace = Depends(current_workspace),
                 db: Session = Depends(get_db)):
    d = db.get(PostDraft, draft_id)
    if d is None or d.workspace_id != ws.id:
        raise HTTPException(404, "post not found")

    async def stream():
        last = None
        for _ in range(200):                      # ~5 min cap
            snap = await asyncio.to_thread(_snapshot, draft_id)
            if snap != last:
                yield f"data: {json.dumps(snap)}\n\n"
                last = snap
            if snap and all(t["status"] in TERMINAL for t in snap):
                yield "event: done\ndata: {}\n\n"
                return
            await asyncio.sleep(1.5)
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
