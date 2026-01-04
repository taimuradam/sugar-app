from pydantic import BaseModel, field_validator
from datetime import date, datetime
from typing import Literal

TxCategory = Literal["principal", "markup"]

class TxCreate(BaseModel):
    date: date
    category: TxCategory = "principal"
    amount: float
    note: str | None = None

    @field_validator("amount")
    @classmethod
    def amount_must_be_finite_and_nonzero(cls, v: float):
        if v is None:
            raise ValueError("amount is required")
        if v != v:
            raise ValueError("amount must be a number")
        if v == float("inf") or v == float("-inf"):
            raise ValueError("amount must be finite")
        if abs(v) < 1e-12:
            raise ValueError("amount must be non-zero")
        return v

    @field_validator("note")
    @classmethod
    def note_trim(cls, v: str | None):
        if v is None:
            return None
        v = v.strip()
        return v or None

class TxOut(BaseModel):
    id: int
    bank_id: int
    date: date
    category: TxCategory
    amount: float
    note: str | None
    created_at: datetime

    class Config:
        from_attributes = True