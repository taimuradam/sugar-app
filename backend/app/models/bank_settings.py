from sqlalchemy import Integer, DateTime, func, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class BankSettings(Base):
    __tablename__ = "bank_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bank_id: Mapped[int] = mapped_column(ForeignKey("banks.id", ondelete="CASCADE"), index=True)

    year: Mapped[int] = mapped_column(Integer, index=True)

    kibor_tenor_months: Mapped[int] = mapped_column(Integer)
    additional_rate: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    kibor_placeholder_rate_percent: Mapped[float] = mapped_column(Numeric(8, 4))
    max_loan_amount: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)

    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("bank_id", "year", name="uq_bank_settings_bank_year"),
    )
