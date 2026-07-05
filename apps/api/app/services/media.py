"""Upload handling: size caps, magic-byte type check, EXIF strip, hashing.

Local-disk storage with an S3-swappable key scheme (workspace/id.ext).
"""
import hashlib
import io
import os

import filetype
from fastapi import HTTPException, UploadFile
from PIL import Image
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import MediaAsset

ALLOWED_MIMES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "video/mp4": ".mp4",
}


def _storage_root() -> str:
    root = get_settings().storage_dir
    os.makedirs(root, exist_ok=True)
    return root


def storage_path(storage_key: str) -> str:
    """Resolve a storage key to an absolute path, refusing anything that would
    escape the storage root (path-traversal defense in depth — keys are
    server-generated, but never trust a DB value you didn't have to)."""
    root = os.path.abspath(_storage_root())
    p = os.path.abspath(os.path.join(root, storage_key))
    if p != root and not p.startswith(root + os.sep):
        raise HTTPException(400, "invalid storage key")
    return p


async def save_upload(db: Session, workspace_id: str, upload: UploadFile) -> MediaAsset:
    s = get_settings()
    raw = await upload.read()
    if len(raw) == 0:
        raise HTTPException(400, "empty file")
    if len(raw) > s.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"file exceeds {s.max_upload_mb} MB limit")

    kind = filetype.guess(raw)  # magic bytes — never trust extension/content-type header
    mime = kind.mime if kind else None
    if mime not in ALLOWED_MIMES:
        raise HTTPException(415, f"unsupported file type ({mime or 'unknown'}); allowed: jpeg, png, mp4")

    width = height = None
    exif_stripped = False
    if mime in ("image/jpeg", "image/png"):
        try:
            img = Image.open(io.BytesIO(raw))
            width, height = img.size
            # Re-encode without metadata => EXIF/GPS stripped
            buf = io.BytesIO()
            if mime == "image/jpeg":
                img.convert("RGB").save(buf, format="JPEG", quality=92)
            else:
                clean = Image.new(img.mode, img.size)
                clean.putdata(list(img.getdata()))
                clean.save(buf, format="PNG")
            raw = buf.getvalue()
            exif_stripped = True
        except Exception:
            raise HTTPException(415, "could not process image file")

    sha = hashlib.sha256(raw).hexdigest()
    asset = MediaAsset(workspace_id=workspace_id, storage_key="", original_name=upload.filename or "upload",
                       mime_type=mime, bytes=len(raw), width=width, height=height,
                       sha256=sha, exif_stripped=exif_stripped)
    db.add(asset)
    db.flush()  # asset.id
    key = f"{workspace_id}/{asset.id}{ALLOWED_MIMES[mime]}"
    os.makedirs(os.path.dirname(storage_path(key)), exist_ok=True)
    with open(storage_path(key), "wb") as f:
        f.write(raw)
    asset.storage_key = key
    return asset


def resolved_media_path(asset: MediaAsset) -> str:
    """Rebuild the on-disk path from server-owned components only.

    basename() strips any traversal characters from the stored filename and the
    directory comes from the asset's own workspace_id (server-generated hex) —
    the request never contributes path material. Final containment check is
    defense in depth.
    """
    root = os.path.abspath(_storage_root())
    filename = os.path.basename(asset.storage_key)
    p = os.path.abspath(os.path.join(root, os.path.basename(asset.workspace_id), filename))
    if not p.startswith(root + os.sep):
        raise HTTPException(400, "invalid storage key")
    return p


def read_media_bytes(asset: MediaAsset) -> bytes:
    with open(resolved_media_path(asset), "rb") as f:
        return f.read()
