from pydantic import BaseModel
from datetime import datetime, date

class BankCreate(BaseModel):
    name: str
    bank_type: str
    kibor_tenor_months: int
    additional_rate: float | None = None
    kibor_placeholder_rate_percent: float = 0.0
    max_loan_amount: float | None = None
    year: int | None = None

class BankOut(BaseModel):
    id: int
    name: str
    bank_type: str
    created_at: datetime

    settings_year: int
    kibor_tenor_months: int
    additional_rate: float | None
    kibor_placeholder_rate_percent: float
    max_loan_amount: float | None
    current_kibor_rate_percent: float | None = None
    current_kibor_effective_date: date | None = None
    current_total_rate_percent: float | None = None

    principal_balance: float = 0.0
    remaining_loan_amount: float | None = None
    loan_utilization_percent: float | None = None

    class Config:
        from_attributes = True