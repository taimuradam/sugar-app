from pydantic import BaseModel
from datetime import date, datetime

class RateCreate(BaseModel):
    effective_date: date
    tenor_months: int
    annual_rate_percent: float

class RateOut(BaseModel):
    id: int
    bank_id: int
    tenor_months: int
    effective_date: date
    annual_rate_percent: float
    created_at: datetime

    class Config:
        from_attributes = True
