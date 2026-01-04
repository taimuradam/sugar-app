from sqlalchemy import Integer, DateTime, func, String, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), index=True)

    username: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)

    entity_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)


Index("ix_audit_logs_entity", AuditLog.entity_type, AuditLog.entity_id)
