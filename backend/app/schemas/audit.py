from pydantic import BaseModel
from datetime import datetime


class AuditOut(BaseModel):
    id: int
    created_at: datetime
    username: str
    action: str
    entity_type: str
    entity_id: int | None
    details: dict | None

    class Config:
        from_attributes = True
