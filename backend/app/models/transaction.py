from sqlalchemy import Integer, Date, DateTime, func, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class Transaction(Base):
    __tablename__ = "transactions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bank_id: Mapped[int] = mapped_column(ForeignKey("banks.id", ondelete="CASCADE"), index=True)
    date: Mapped[Date] = mapped_column(Date, index=True)
    category: Mapped[str] = mapped_column(String(16), default="principal")
    amount: Mapped[float] = mapped_column(Numeric(14, 2))
    note: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
