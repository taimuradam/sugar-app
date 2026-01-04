from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog


def log_event(
    s: Session,
    username: str,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    details: dict | None = None,
):
    row = AuditLog(
        username=username,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    )
    s.add(row)
    s.commit()
    return row
