from pydantic import BaseModel
from datetime import datetime

class LoanCreate(BaseModel):
    name: str
    kibor_tenor_months: int  # 1 | 3 | 6
    additional_rate: float | None = None
    kibor_placeholder_rate_percent: float = 0.0
    max_loan_amount: float | None = None

class LoanOut(BaseModel):
    id: int
    bank_id: int
    name: str
    kibor_tenor_months: int
    additional_rate: float | None
    kibor_placeholder_rate_percent: float
    max_loan_amount: float | None
    created_at: datetime | None = None

    class Config:
        from_attributes = True

class LoanBalanceOut(BaseModel):
    bank_id: int
    loan_id: int
    principal_balance: float
    as_of: datetime | None = None