"""GitHub integration: encrypted PAT storage + filtered project-folder upload.

Security model:
- The PAT is validated against GitHub, then stored AES-256-GCM-encrypted like
  every other platform token; it never returns to the browser.
- Upload filtering runs client-side (speed) AND server-side (trust): secrets
  (.env*), dependency/cache dirs, and oversized files are always excluded here
  regardless of what the client sends. Path traversal is rejected.
"""
import base64
import logging
import posixpath

import httpx
from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ConnectedAccount, Workspace, utcnow
from ..security.crypto import TokenCryptoError, decrypt_token, encrypt_token
from ..security.ratelimit import rate_limit
from ..security.sessions import current_user, current_workspace
from ..services.audit import write_audit

log = logging.getLogger("github")
router = APIRouter(prefix="/github", tags=["github"])

GH = "https://api.github.com"

# --- server-side upload filters (defense in depth — client filters too) ---
EXCLUDED_DIRS = {".git", "node_modules", ".next", "__pycache__", ".venv", "venv",
                 "data", "storage", ".pytest_cache", ".mypy_cache", ".claude", "dist", "build", "out"}
EXCLUDED_FILE_PREFIXES = (".env",)                      # .env, .env.local, ... NEVER uploaded
EXCLUDED_FILE_SUFFIXES = (".pyc", ".log", ".sqlite", ".db", ".DS_Store", ".tsbuildinfo")
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_TOTAL_BYTES = 25 * 1024 * 1024
MAX_FILES = 400


def _gh_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"}


def _excluded(path: str) -> str | None:
    """Returns a human-readable reason if the path must be excluded."""
    norm = posixpath.normpath(path.replace("\\", "/")).lstrip("/")
    if norm.startswith("..") or "/../" in f"/{norm}/":
        return "path traversal"
    parts = norm.split("/")
    for part in parts[:-1]:
        if part in EXCLUDED_DIRS:
            return f"inside {part}/"
    name = parts[-1]
    if name in EXCLUDED_DIRS:
        return "excluded directory"
    if any(name.startswith(p) for p in EXCLUDED_FILE_PREFIXES):
        return "secret file (.env*)"
    if any(name.endswith(s) for s in EXCLUDED_FILE_SUFFIXES):
        return "generated/temporary file"
    return None


def _github_account(ws: Workspace, db: Session) -> ConnectedAccount:
    acc = (db.query(ConnectedAccount)
             .filter(ConnectedAccount.workspace_id == ws.id,
                     ConnectedAccount.platform == "github",
                     ConnectedAccount.status == "active").first())
    if acc is None:
        raise HTTPException(400, "GitHub is not connected — add your API token in Settings first")
    return acc


class TokenBody(BaseModel):
    token: str


@router.post("/token")
def save_token(body: TokenBody, ws: Workspace = Depends(current_workspace),
               user=Depends(current_user), db: Session = Depends(get_db),
               _rl=Depends(rate_limit("gh_token", 5, 60))):
    token = body.token.strip()
    if len(token) < 20:
        raise HTTPException(400, "that doesn't look like a GitHub token")
    try:
        r = httpx.get(f"{GH}/user", headers=_gh_headers(token), timeout=20)
    except httpx.HTTPError:
        raise HTTPException(502, "could not reach GitHub — try again")
    if r.status_code != 200:
        raise HTTPException(400, "GitHub rejected this token — check it has repo permissions and isn't expired")
    info = r.json()
    login = info.get("login", "")

    enc, ver = encrypt_token(token)
    acc = (db.query(ConnectedAccount)
             .filter(ConnectedAccount.workspace_id == ws.id,
                     ConnectedAccount.platform == "github",
                     ConnectedAccount.external_account_id == login).first())
    if acc is None:
        acc = ConnectedAccount(workspace_id=ws.id, platform="github", external_account_id=login)
        db.add(acc)
    acc.account_name = info.get("name") or login
    acc.enc_access_token = enc
    acc.key_version = ver
    acc.scopes = "api-token"
    acc.status = "active"
    write_audit(db, action="account_connected", workspace_id=ws.id, actor_user_id=user.id,
                entity_type="connected_account", entity_id=acc.id or "", platform="github")
    db.commit()
    return {"login": login, "name": acc.account_name}


@router.post("/upload")
async def upload_project(repo: str = Form(...), private: bool = Form(True),
                         commit_message: str = Form("Upload via Social Poster"),
                         paths: str = Form(...),   # JSON array of relative paths, same order as files
                         files: list[UploadFile] = None,
                         ws: Workspace = Depends(current_workspace),
                         user=Depends(current_user), db: Session = Depends(get_db),
                         _rl=Depends(rate_limit("gh_upload", 3, 60))):
    import json as _json
    import re as _re
    if files is None:
        files = []
    if not _re.fullmatch(r"[A-Za-z0-9._-]{1,100}", repo):
        raise HTTPException(400, "repo name: letters, numbers, dots, dashes, underscores only")
    try:
        path_list = _json.loads(paths)
        assert isinstance(path_list, list) and len(path_list) == len(files)
    except Exception:
        raise HTTPException(400, "paths must be a JSON array matching the files")
    if len(files) > MAX_FILES:
        raise HTTPException(413, f"too many files after filtering (max {MAX_FILES})")

    acc = _github_account(ws, db)
    try:
        token = decrypt_token(acc.enc_access_token, acc.key_version)
    except TokenCryptoError:
        raise HTTPException(500, "stored GitHub token could not be decrypted — reconnect GitHub")

    # read + filter (server-side, authoritative)
    to_upload: list[tuple[str, bytes]] = []
    skipped: list[dict] = []
    total = 0
    for path, f in zip(path_list, files):
        reason = _excluded(str(path))
        data = await f.read()
        if reason:
            skipped.append({"path": path, "reason": reason})
            continue
        if len(data) > MAX_FILE_BYTES:
            skipped.append({"path": path, "reason": f"larger than {MAX_FILE_BYTES // 1024 // 1024} MB"})
            continue
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise HTTPException(413, f"upload exceeds {MAX_TOTAL_BYTES // 1024 // 1024} MB total — trim the folder")
        norm = posixpath.normpath(str(path).replace("\\", "/")).lstrip("/")
        to_upload.append((norm, data))
    if not to_upload:
        raise HTTPException(400, "nothing left to upload after filtering")

    async with httpx.AsyncClient(timeout=60, headers=_gh_headers(token)) as gh:
        login_r = await gh.get(f"{GH}/user")
        if login_r.status_code != 200:
            raise HTTPException(400, "GitHub token no longer valid — reconnect GitHub")
        login = login_r.json()["login"]

        # ensure repo exists (auto_init gives us a base commit to build on)
        repo_r = await gh.get(f"{GH}/repos/{login}/{repo}")
        if repo_r.status_code == 404:
            create = await gh.post(f"{GH}/user/repos",
                                   json={"name": repo, "private": private, "auto_init": True,
                                         "description": "Uploaded with Social Poster"})
            if create.status_code not in (200, 201):
                raise HTTPException(502, f"could not create repo (HTTP {create.status_code})")
            repo_info = create.json()
        elif repo_r.status_code == 200:
            repo_info = repo_r.json()
        else:
            raise HTTPException(502, f"could not check repo (HTTP {repo_r.status_code})")
        branch = repo_info.get("default_branch", "main")
        full = f"{GH}/repos/{login}/{repo}"

        # base commit (retry briefly: auto_init commit can lag a moment)
        base_commit_sha = base_tree_sha = None
        for _ in range(5):
            ref_r = await gh.get(f"{full}/git/ref/heads/{branch}")
            if ref_r.status_code == 200:
                base_commit_sha = ref_r.json()["object"]["sha"]
                commit_r = await gh.get(f"{full}/git/commits/{base_commit_sha}")
                base_tree_sha = commit_r.json()["tree"]["sha"] if commit_r.status_code == 200 else None
                break
            import asyncio; await asyncio.sleep(1)
        if not base_commit_sha:
            raise HTTPException(502, "repo has no base commit yet — try again in a few seconds")

        # blobs -> tree -> commit -> ref
        tree_entries = []
        for norm, data in to_upload:
            blob = await gh.post(f"{full}/git/blobs",
                                 json={"content": base64.b64encode(data).decode(), "encoding": "base64"})
            if blob.status_code not in (200, 201):
                raise HTTPException(502, f"blob upload failed for {norm} (HTTP {blob.status_code})")
            tree_entries.append({"path": norm, "mode": "100644", "type": "blob",
                                 "sha": blob.json()["sha"]})
        tree = await gh.post(f"{full}/git/trees",
                             json={"base_tree": base_tree_sha, "tree": tree_entries})
        if tree.status_code not in (200, 201):
            raise HTTPException(502, f"tree creation failed (HTTP {tree.status_code})")
        commit = await gh.post(f"{full}/git/commits",
                               json={"message": commit_message[:200],
                                     "tree": tree.json()["sha"], "parents": [base_commit_sha]})
        if commit.status_code not in (200, 201):
            raise HTTPException(502, f"commit failed (HTTP {commit.status_code})")
        ref = await gh.patch(f"{full}/git/refs/heads/{branch}",
                             json={"sha": commit.json()["sha"], "force": False})
        if ref.status_code != 200:
            raise HTTPException(502, f"branch update failed (HTTP {ref.status_code})")

    write_audit(db, action="github_project_uploaded", workspace_id=ws.id, actor_user_id=user.id,
                platform="github", meta={"repo": repo, "files": len(to_upload),
                                         "skipped": len(skipped), "bytes": total})
    db.commit()
    return {"repo_url": repo_info.get("html_url", f"https://github.com/{login}/{repo}"),
            "branch": branch, "files_uploaded": len(to_upload),
            "bytes_uploaded": total, "skipped": skipped[:50]}
