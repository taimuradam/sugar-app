from sqlalchemy import String, Integer, DateTime, func, Numeric
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class Bank(Base):
    __tablename__ = "banks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    bank_type: Mapped[str] = mapped_column(String(16))
    additional_rate: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
