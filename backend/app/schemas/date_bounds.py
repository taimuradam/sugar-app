from pydantic import BaseModel
from datetime import date

class LoanDateBoundsOut(BaseModel):
    min_date: date | None = None
    max_date: date | None = None
