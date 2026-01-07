from __future__ import annotations

from pydantic import BaseModel
from typing import Literal, Optional


class BackfillStatusOut(BaseModel):
    status: Literal["idle", "running", "done", "error"] = "idle"
    total_days: int = 0
    processed_days: int = 0
    started_at: Optional[str] = None
    updated_at: Optional[str] = None
    message: Optional[str] = None
