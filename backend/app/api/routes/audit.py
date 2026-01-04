from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime
from app.api.deps import db, require_admin
from app.models.audit_log import AuditLog
from app.schemas.audit import AuditOut

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditOut])
def list_audit(
    s: Session = Depends(db),
    admin=Depends(require_admin),
    username: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    action: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
):
    q = select(AuditLog).order_by(AuditLog.created_at.desc())

    if username:
        q = q.where(AuditLog.username == username)
    if entity_type:
        q = q.where(AuditLog.entity_type == entity_type)
    if action:
        q = q.where(AuditLog.action == action)

    q = q.limit(limit)
    return s.execute(q).scalars().all()
