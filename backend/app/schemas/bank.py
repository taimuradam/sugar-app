from pydantic import BaseModel
from datetime import datetime

class BankCreate(BaseModel):
    name: str
    bank_type: str
    additional_rate: float | None = None

class BankOut(BaseModel):
    id: int
    name: str
    bank_type: str
    additional_rate: float | None
    created_at: datetime

    class Config:
        from_attributes = True
