from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from datetime import date
from sqlalchemy.orm import Session

from app.api.deps import db, current_user
from app.schemas.backfill import BackfillStatusOut
from app.schemas.ledger import LedgerRow
from app.services.ledger import compute_ledger
from app.services.kibor_backfill import is_ready, ensure_started, get_status

router = APIRouter(prefix="/banks/{bank_id}/loans/{loan_id}/ledger", tags=["ledger"])


@router.get("", response_model=list[LedgerRow])
def ledger(
    bank_id: int,
    loan_id: int,
    start: date = Query(...),
    end: date = Query(...),
    s: Session = Depends(db),
    u=Depends(current_user),
):
    if not is_ready(s, bank_id, loan_id):
        st = get_status(bank_id, loan_id)
        if st.get("status") != "running":
            st = ensure_started(bank_id, loan_id)
        return JSONResponse(status_code=202, content=BackfillStatusOut(**st).model_dump())

    rows = compute_ledger(s, bank_id, loan_id, start, end)
    return [LedgerRow(**r) for r in rows]