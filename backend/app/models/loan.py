from sqlalchemy import Integer, DateTime, func, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class Loan(Base):
    __tablename__ = "loans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bank_id: Mapped[int] = mapped_column(ForeignKey("banks.id", ondelete="CASCADE"), index=True)

    name: Mapped[str] = mapped_column(String(128))
    kibor_tenor_months: Mapped[int] = mapped_column(Integer)
    additional_rate: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    kibor_placeholder_rate_percent: Mapped[float] = mapped_column(Numeric(8, 4), server_default="0.0")
    max_loan_amount: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)

    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("bank_id", "name", name="uq_loans_bank_name"),
    )
