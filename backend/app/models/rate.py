from sqlalchemy import Integer, Date, DateTime, func, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class Rate(Base):
    __tablename__ = "rates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bank_id: Mapped[int] = mapped_column(ForeignKey("banks.id", ondelete="CASCADE"), index=True)
    effective_date: Mapped[Date] = mapped_column(Date, index=True)
    annual_rate_percent: Mapped[float] = mapped_column(Numeric(8, 4))
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
