"""LinkedIn OAuth 2.0 (Authorization Code, confidential client, server-side only)."""
import logging
from datetime import timedelta
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import ConnectedAccount, OAuthState, User, Workspace, utcnow
from ..security.crypto import encrypt_token, new_state
from ..security.ratelimit import rate_limit
from ..security.sessions import current_user, current_workspace
from ..services.audit import write_audit

log = logging.getLogger("oauth.linkedin")
router = APIRouter(prefix="/oauth/linkedin", tags=["oauth"])

AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
STATE_TTL_MIN = 10


@router.get("/config")
def config(user: User = Depends(current_user)):
    """Non-secret config so the UI can show the EXACT redirect URL to register
    in the LinkedIn app (mismatches are the #1 OAuth failure)."""
    s = get_settings()
    return {
        "redirect_uri": s.linkedin_redirect_uri,
        "client_id_configured": bool(s.linkedin_client_id),
        "secret_configured": bool(s.linkedin_client_secret),
        "scopes": s.linkedin_scopes,
        "api_version": s.linkedin_api_version,
    }


@router.post("/start")
def start(user: User = Depends(current_user), db: Session = Depends(get_db),
          _rl=Depends(rate_limit("oauth_start", 10, 60))):
    s = get_settings()
    if not s.linkedin_client_id or not s.linkedin_client_secret:
        raise HTTPException(500, "LinkedIn is not configured — set LINKEDIN_CLIENT_ID / LINKEDIN_CLIENT_SECRET in apps/api/.env")
    if not s.linkedin_redirect_uri:
        raise HTTPException(500, "LINKEDIN_REDIRECT_URI is empty — set it in apps/api/.env")
    state = new_state()
    db.add(OAuthState(state=state, user_id=user.id, provider="linkedin",
                      expires_at=utcnow() + timedelta(minutes=STATE_TTL_MIN)))
    db.commit()
    q = urlencode({
        "response_type": "code",
        "client_id": s.linkedin_client_id,
        "redirect_uri": s.linkedin_redirect_uri,
        "state": state,
        "scope": s.linkedin_scopes,
    })
    return {"authorize_url": f"{AUTH_URL}?{q}"}


@router.get("/callback")
def callback(request: Request, code: str | None = None, state: str | None = None,
             error: str | None = None, error_description: str | None = None,
             user: User = Depends(current_user),
             ws: Workspace = Depends(current_workspace),
             db: Session = Depends(get_db)):
    s = get_settings()
    web = s.web_origin

    if error:
        log.warning("linkedin oauth denied: %s", error)
        return RedirectResponse(f"{web}/settings?error=linkedin_denied", status_code=303)
    if not code or not state:
        return RedirectResponse(f"{web}/settings?error=linkedin_missing_params", status_code=303)

    # CSRF check: state must exist, belong to THIS user, be unexpired — and is single-use.
    row = db.get(OAuthState, state)
    if row is None or row.provider != "linkedin" or row.user_id != user.id or row.expires_at < utcnow():
        if row is not None:
            db.delete(row); db.commit()
        raise HTTPException(400, "invalid or expired OAuth state")
    db.delete(row); db.commit()

    try:
        with httpx.Client(timeout=30) as client:
            tr = client.post(TOKEN_URL, data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": s.linkedin_redirect_uri,
                "client_id": s.linkedin_client_id,
                "client_secret": s.linkedin_client_secret,
            }, headers={"Content-Type": "application/x-www-form-urlencoded"})
            if tr.status_code != 200:
                log.warning("linkedin token exchange failed: %s", tr.status_code)
                return RedirectResponse(f"{web}/settings?error=linkedin_token_exchange", status_code=303)
            tok = tr.json()
            access_token = tok.get("access_token", "")
            expires_in = int(tok.get("expires_in", 0) or 0)
            refresh_token = tok.get("refresh_token")

            ui = client.get(USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
            if ui.status_code != 200:
                return RedirectResponse(f"{web}/settings?error=linkedin_userinfo", status_code=303)
            info = ui.json()
    except httpx.HTTPError:
        return RedirectResponse(f"{web}/settings?error=linkedin_network", status_code=303)

    sub = info.get("sub", "")
    if not sub:
        return RedirectResponse(f"{web}/settings?error=linkedin_no_sub", status_code=303)
    person_urn = f"urn:li:person:{sub}"
    name = info.get("name") or info.get("given_name", "LinkedIn user")

    enc_access, key_version = encrypt_token(access_token)
    enc_refresh = encrypt_token(refresh_token)[0] if refresh_token else None
    expires_at = utcnow() + timedelta(seconds=expires_in) if expires_in else None

    account = (db.query(ConnectedAccount)
                 .filter(ConnectedAccount.workspace_id == ws.id,
                         ConnectedAccount.platform == "linkedin",
                         ConnectedAccount.external_account_id == person_urn).first())
    if account is None:
        account = ConnectedAccount(workspace_id=ws.id, platform="linkedin",
                                   external_account_id=person_urn)
        db.add(account)
    account.account_name = name
    account.enc_access_token = enc_access
    account.enc_refresh_token = enc_refresh
    account.key_version = key_version
    account.scopes = s.linkedin_scopes
    account.token_expires_at = expires_at
    account.status = "active"
    write_audit(db, action="account_connected", workspace_id=ws.id, actor_user_id=user.id,
                entity_type="connected_account", entity_id=account.id or "", platform="linkedin",
                ip=request.client.host if request.client else "")
    db.commit()
    return RedirectResponse(f"{web}/settings?connected=linkedin", status_code=303)
