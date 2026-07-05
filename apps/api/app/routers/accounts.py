import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import ConnectedAccount, Workspace
from ..security.crypto import TokenCryptoError, decrypt_token
from ..security.sessions import current_user, current_workspace
from ..services.audit import write_audit

router = APIRouter(prefix="/connected-accounts", tags=["accounts"])


@router.get("")
def list_accounts(ws: Workspace = Depends(current_workspace), db: Session = Depends(get_db)):
    rows = db.query(ConnectedAccount).filter(ConnectedAccount.workspace_id == ws.id).all()
    return [{
        "id": a.id, "platform": a.platform, "account_name": a.account_name,
        "external_account_id": a.external_account_id, "status": a.status,
        "scopes": a.scopes,
        "token_expires_at": a.token_expires_at.isoformat() + "Z" if a.token_expires_at else None,
    } for a in rows]  # tokens never leave the server


@router.delete("/{account_id}")
def disconnect(account_id: str, ws: Workspace = Depends(current_workspace),
               user=Depends(current_user), db: Session = Depends(get_db)):
    a = db.get(ConnectedAccount, account_id)
    if a is None or a.workspace_id != ws.id:
        raise HTTPException(404, "account not found")
    # best-effort provider-side revoke (LinkedIn)
    if a.platform == "linkedin":
        s = get_settings()
        try:
            token = decrypt_token(a.enc_access_token, a.key_version)
            httpx.post("https://www.linkedin.com/oauth/v2/revoke",
                       data={"client_id": s.linkedin_client_id,
                             "client_secret": s.linkedin_client_secret,
                             "token": token},
                       headers={"Content-Type": "application/x-www-form-urlencoded"},
                       timeout=15)
        except (TokenCryptoError, httpx.HTTPError):
            pass  # local removal still proceeds
    write_audit(db, action="account_disconnected", workspace_id=ws.id, actor_user_id=user.id,
                entity_type="connected_account", entity_id=a.id, platform=a.platform)
    db.delete(a)
    db.commit()
    return {"ok": True}
