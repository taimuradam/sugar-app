from pydantic import BaseModel
from datetime import date

class LedgerRow(BaseModel):
    date: date
    principal_balance: float
    daily_markup: float
    accrued_markup: float
    rate_percent: float
