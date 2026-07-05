"""Signed session cookies: httpOnly + SameSite=Lax; Secure outside dev."""
from fastapi import Depends, HTTPException, Request, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import User, Workspace

COOKIE_NAME = "sp_session"


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().session_secret, salt="session-v1")


def set_session_cookie(response: Response, user_id: str) -> None:
    s = get_settings()
    token = _serializer().dumps({"uid": user_id})
    response.set_cookie(
        COOKIE_NAME, token,
        max_age=s.session_max_age_s, httponly=True, samesite="lax",
        secure=(s.app_env != "dev"), path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="not authenticated")
    try:
        data = _serializer().loads(token, max_age=get_settings().session_max_age_s)
    except (BadSignature, SignatureExpired):
        raise HTTPException(status_code=401, detail="invalid session")
    user = db.get(User, data.get("uid", ""))
    if not user:
        raise HTTPException(status_code=401, detail="unknown user")
    return user


def current_workspace(user: User = Depends(current_user), db: Session = Depends(get_db)) -> Workspace:
    ws = db.query(Workspace).filter(Workspace.owner_user_id == user.id).first()
    if not ws:
        raise HTTPException(status_code=500, detail="workspace missing")
    return ws
