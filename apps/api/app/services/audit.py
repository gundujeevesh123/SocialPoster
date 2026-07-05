from sqlalchemy.orm import Session

from ..models import AuditLog, Notification


def write_audit(db: Session, *, action: str, workspace_id: str | None = None,
                actor_user_id: str | None = None, entity_type: str = "",
                entity_id: str = "", platform: str = "", ip: str = "",
                meta: dict | None = None) -> None:
    db.add(AuditLog(action=action, workspace_id=workspace_id, actor_user_id=actor_user_id,
                    entity_type=entity_type, entity_id=entity_id, platform=platform,
                    ip=ip, meta=meta))


def notify(db: Session, *, user_id: str, type: str, payload: dict | None = None) -> None:
    db.add(Notification(user_id=user_id, type=type, payload=payload))
