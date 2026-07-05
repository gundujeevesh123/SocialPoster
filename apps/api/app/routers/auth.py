import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import User, Workspace
from ..security.passwords import hash_password, verify_password
from ..security.ratelimit import rate_limit
from ..security.sessions import clear_session_cookie, current_user, set_session_cookie
from ..services.audit import write_audit

router = APIRouter(prefix="/auth", tags=["auth"])
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class Credentials(BaseModel):
    email: str
    password: str


@router.post("/register", status_code=201)
def register(body: Credentials, request: Request, response: Response,
             db: Session = Depends(get_db),
             _rl=Depends(rate_limit("register", 10, 60))):
    s = get_settings()
    email = body.email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(400, "invalid email address")
    if len(body.password) < s.min_password_len:
        raise HTTPException(400, f"password must be at least {s.min_password_len} characters")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "an account with this email already exists")
    user = User(email=email, password_hash=hash_password(body.password))
    db.add(user); db.flush()
    db.add(Workspace(name="Personal", owner_user_id=user.id))
    write_audit(db, action="user_registered", actor_user_id=user.id,
                ip=request.client.host if request.client else "")
    db.commit()
    set_session_cookie(response, user.id)
    return {"id": user.id, "email": user.email}


@router.post("/login")
def login(body: Credentials, request: Request, response: Response,
          db: Session = Depends(get_db),
          _rl=Depends(rate_limit("login", get_settings().login_rate_per_min, 60))):
    email = body.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(user.password_hash, body.password):
        raise HTTPException(401, "invalid email or password")   # generic on purpose
    write_audit(db, action="user_login", actor_user_id=user.id,
                ip=request.client.host if request.client else "")
    db.commit()
    set_session_cookie(response, user.id)
    return {"id": user.id, "email": user.email}


@router.post("/logout")
def logout(response: Response, user: User = Depends(current_user)):
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "email": user.email}
