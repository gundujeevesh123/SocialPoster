from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import MediaAsset, Workspace
from ..security.ratelimit import rate_limit
from ..security.sessions import current_workspace
from ..services import media as media_svc
from ..services.audit import write_audit

router = APIRouter(prefix="/media", tags=["media"])


def _owned_asset(asset_id: str, ws: Workspace, db: Session) -> MediaAsset:
    asset = db.get(MediaAsset, asset_id)
    if asset is None or asset.workspace_id != ws.id:   # 404, not 403 — don't leak existence
        raise HTTPException(404, "media not found")
    return asset


@router.post("/upload", status_code=201)
async def upload(file: UploadFile, ws: Workspace = Depends(current_workspace),
                 db: Session = Depends(get_db),
                 _rl=Depends(rate_limit("upload", 20, 60))):
    asset = await media_svc.save_upload(db, ws.id, file)
    write_audit(db, action="media_uploaded", workspace_id=ws.id,
                entity_type="media_asset", entity_id=asset.id,
                meta={"mime": asset.mime_type, "bytes": asset.bytes})
    db.commit()
    return {"id": asset.id, "mime_type": asset.mime_type, "bytes": asset.bytes,
            "width": asset.width, "height": asset.height,
            "original_name": asset.original_name, "exif_stripped": asset.exif_stripped}


@router.get("/{asset_id}")
def meta(asset_id: str, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    a = _owned_asset(asset_id, ws, db)
    return {"id": a.id, "mime_type": a.mime_type, "bytes": a.bytes,
            "width": a.width, "height": a.height, "original_name": a.original_name}


@router.get("/{asset_id}/file")
def file(asset_id: str, ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    a = _owned_asset(asset_id, ws, db)
    return FileResponse(media_svc.resolved_media_path(a), media_type=a.mime_type)
