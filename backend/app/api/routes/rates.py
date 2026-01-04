from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.api.deps import db, current_user, require_admin
from app.schemas.rate import RateCreate, RateOut
from app.models.rate import Rate
from app.services.audit import log_event

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

    log_event(
        s,
        username=u.get("sub"),
        action="rate.create",
        entity_type="rate",
        entity_id=r.id,
        details={
            "bank_id": bank_id,
            "effective_date": str(r.effective_date),
            "annual_rate_percent": str(r.annual_rate_percent),
        },
    )
    return r

@router.delete("/{rate_id}")
def delete_rate(bank_id: int, rate_id: int, s: Session = Depends(db), u=Depends(require_admin)):
    r = s.execute(select(Rate).where(Rate.id == rate_id, Rate.bank_id == bank_id)).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="rate_not_found")
    
    details = {
        "bank_id": bank_id,
        "effective_date": str(r.effective_date),
        "annual_rate_percent": str(r.annual_rate_percent),
    }
    s.delete(r)
    s.commit()

    log_event(
        s,
        username=u.get("sub"),
        action="rate.delete",
        entity_type="rate",
        entity_id=rate_id,
        details=details,
    )
    return {"ok": True}