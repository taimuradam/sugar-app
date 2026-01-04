from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.api.deps import db, current_user, require_admin
from app.schemas.rate import RateCreate, RateOut
from app.models.rate import Rate

router = APIRouter(prefix="/banks/{bank_id}/rates", tags=["rates"])

@router.get("", response_model=list[RateOut])
def list_rates(bank_id: int, s: Session = Depends(db), u=Depends(current_user)):
    return s.execute(select(Rate).where(Rate.bank_id == bank_id).order_by(Rate.effective_date.asc())).scalars().all()

@router.post("", response_model=RateOut)
def add_rate(bank_id: int, body: RateCreate, s: Session = Depends(db), u=Depends(require_admin)):
    r = Rate(bank_id=bank_id, effective_date=body.effective_date, annual_rate_percent=body.annual_rate_percent)
    s.add(r)
    s.commit()
    s.refresh(r)
    return r
