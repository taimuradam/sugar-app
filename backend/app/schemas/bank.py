from pydantic import BaseModel
from datetime import datetime

class BankCreate(BaseModel):
    name: str
    bank_type: str  # "conventional" | "islamic"

class BankOut(BaseModel):
    id: int
    name: str
    bank_type: str
    created_at: datetime | None = None

    class Config:
        from_attributes = True
