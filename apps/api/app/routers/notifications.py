from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Notification, User, utcnow
from ..security.sessions import current_user

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(unread_only: bool = False, user: User = Depends(current_user),
                       db: Session = Depends(get_db)):
    q = db.query(Notification).filter(Notification.user_id == user.id)
    if unread_only:
        q = q.filter(Notification.read_at.is_(None))
    rows = q.order_by(Notification.created_at.desc()).limit(50).all()
    return [{"id": n.id, "type": n.type, "payload": n.payload,
             "read": n.read_at is not None,
             "created_at": n.created_at.isoformat() + "Z"} for n in rows]


@router.post("/{notification_id}/read")
def mark_read(notification_id: str, user: User = Depends(current_user),
              db: Session = Depends(get_db)):
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user.id:
        raise HTTPException(404, "notification not found")
    n.read_at = utcnow()
    db.commit()
    return {"ok": True}
