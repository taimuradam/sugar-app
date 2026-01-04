from fastapi import APIRouter, Depends, Query
from datetime import date
from sqlalchemy.orm import Session
from app.api.deps import db, current_user
from app.schemas.ledger import LedgerRow
from app.services.ledger import compute_ledger

router = APIRouter(prefix="/banks/{bank_id}/ledger", tags=["ledger"])

@router.get("", response_model=list[LedgerRow])
def ledger(
    bank_id: int,
    start: date = Query(...),
    end: date = Query(...),
    s: Session = Depends(db),
    u=Depends(current_user),
):
    return compute_ledger(s, bank_id, start, end)
