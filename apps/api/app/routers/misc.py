from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..security.sessions import current_user
from ..services.captions import LIMITS, SUPPORTED_PLATFORMS, generate_captions

router = APIRouter(tags=["misc"])


@router.get("/healthz")
def healthz():
    return {"ok": True}


@router.get("/platforms")
def platforms(user=Depends(current_user)):
    from ..config import get_settings
    s = get_settings()
    real = {"linkedin": s.enable_linkedin_real, "facebook": s.enable_facebook_real,
            "twitter": s.enable_twitter_real, "youtube": s.enable_youtube_real}
    return [{"platform": p, "mode": "real" if real.get(p) else "mock", "limits": LIMITS[p]}
            for p in SUPPORTED_PLATFORMS]


class CaptionReq(BaseModel):
    master_caption: str
    platforms: list[str]


@router.post("/captions/generate")
def captions(body: CaptionReq, user=Depends(current_user)):
    ps = [p for p in body.platforms if p in SUPPORTED_PLATFORMS]
    return generate_captions(body.master_caption, ps)
