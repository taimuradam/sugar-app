from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from datetime import date
from sqlalchemy.orm import Session

from app.api.deps import db, current_user
from app.schemas.ledger import LedgerRow
from app.schemas.backfill import BackfillStatusOut
from app.services.ledger import compute_ledger
from app.services.kibor_backfill import is_ready, ensure_started, get_status

router = APIRouter(prefix="/banks/{bank_id}/ledger", tags=["ledger"])


@router.get("", response_model=list[LedgerRow])
def ledger(
    bank_id: int,
    start: date = Query(...),
    end: date = Query(...),
    s: Session = Depends(db),
    u=Depends(current_user),
):
    # If KIBOR backfill is needed (common after backdated principal debits),
    # start it in the background and return 202 so the UI can show progress.
    if not is_ready(s, bank_id):
        st = get_status(bank_id)
        if st.get("status") != "running":
            st = ensure_started(bank_id)
        return JSONResponse(status_code=202, content=BackfillStatusOut(**st).model_dump())

    return compute_ledger(s, bank_id, start, end)
