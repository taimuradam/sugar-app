from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from datetime import date
from io import BytesIO
from sqlalchemy.orm import Session
from app.api.deps import db, current_user
from app.services.reports import build_bank_report

router = APIRouter(prefix="/banks/{bank_id}/report", tags=["reports"])

@router.get("")
def report(
    bank_id: int,
    start: date = Query(...),
    end: date = Query(...),
    s: Session = Depends(db),
    u=Depends(current_user),
):
    buf = BytesIO()
    build_bank_report(s, bank_id, start, end, buf)
    buf.seek(0)
    filename = f"bank_{bank_id}_{start}_to_{end}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
