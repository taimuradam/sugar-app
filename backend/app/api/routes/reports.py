from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from datetime import date
from io import BytesIO
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.api.deps import db, current_user
from app.models.loan import Loan
from app.schemas.backfill import BackfillStatusOut
from app.services.kibor_backfill import is_ready, ensure_started, get_status
from app.services.reports import build_loan_report

router = APIRouter(prefix="/banks/{bank_id}/report", tags=["reports"])


def _pick_default_loan_id(s: Session, bank_id: int) -> int:
    ln = (
        s.execute(select(Loan).where(Loan.bank_id == bank_id).order_by(Loan.created_at.asc(), Loan.id.asc()))
        .scalars()
        .first()
    )
    if ln is None:
        raise HTTPException(status_code=404, detail="loan_not_found")
    return ln.id


@router.get("")
def report(
    bank_id: int,
    start: date = Query(...),
    end: date = Query(...),
    loan_id: int | None = Query(None),
    s: Session = Depends(db),
    u=Depends(current_user),
):
    lid = loan_id if loan_id is not None else _pick_default_loan_id(s, bank_id)

    if not is_ready(s, bank_id, lid):
        st = get_status(bank_id, lid)
        if st.get("status") != "running":
            st = ensure_started(bank_id, lid)
        return JSONResponse(status_code=202, content=BackfillStatusOut(**st).model_dump())

    buf = BytesIO()
    build_loan_report(s, bank_id, lid, start, end, buf)
    buf.seek(0)

    filename = f"bank_{bank_id}_loan_{lid}_{start}_to_{end}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )