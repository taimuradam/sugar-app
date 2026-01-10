from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.api.deps import db, current_user, require_admin
from app.models.bank import Bank
from app.models.loan import Loan
from app.schemas.loan import LoanCreate, LoanOut
from app.services.audit import log_event

router = APIRouter(prefix="/banks/{bank_id}/loans", tags=["loans"])


def _require_bank(s: Session, bank_id: int) -> Bank:
    b = s.execute(select(Bank).where(Bank.id == bank_id)).scalar_one_or_none()
    if b is None:
        raise HTTPException(status_code=404, detail="bank_not_found")
    return b


@router.get("", response_model=list[LoanOut])
def list_loans(bank_id: int, s: Session = Depends(db), u=Depends(current_user)):
    _require_bank(s, bank_id)
    return s.execute(select(Loan).where(Loan.bank_id == bank_id).order_by(Loan.created_at.asc(), Loan.id.asc())).scalars().all()


@router.post("", response_model=LoanOut)
def create_loan(bank_id: int, body: LoanCreate, s: Session = Depends(db), u=Depends(require_admin)):
    _require_bank(s, bank_id)

    nm = body.name.strip()
    if not nm:
        raise HTTPException(status_code=400, detail="loan_name_required")
    if body.kibor_tenor_months not in (1, 3, 6):
        raise HTTPException(status_code=400, detail="kibor_tenor_invalid")

    exists = s.execute(select(Loan).where(Loan.bank_id == bank_id, Loan.name == nm)).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="loan_exists")

    ln = Loan(
        bank_id=bank_id,
        name=nm,
        kibor_tenor_months=int(body.kibor_tenor_months),
        additional_rate=body.additional_rate,
        kibor_placeholder_rate_percent=body.kibor_placeholder_rate_percent,
        max_loan_amount=body.max_loan_amount,
    )
    s.add(ln)
    s.commit()
    s.refresh(ln)

    log_event(
        s,
        username=u.get("sub"),
        action="loan.create",
        entity_type="loan",
        entity_id=ln.id,
        details={
            "bank_id": bank_id,
            "name": ln.name,
            "kibor_tenor_months": ln.kibor_tenor_months,
            "additional_rate": str(ln.additional_rate) if ln.additional_rate is not None else None,
            "kibor_placeholder_rate_percent": str(ln.kibor_placeholder_rate_percent),
            "max_loan_amount": str(ln.max_loan_amount) if ln.max_loan_amount is not None else None,
        },
    )
    return ln


@router.delete("/{loan_id}")
def delete_loan(bank_id: int, loan_id: int, s: Session = Depends(db), u=Depends(require_admin)):
    _require_bank(s, bank_id)
    ln = s.execute(select(Loan).where(Loan.id == loan_id, Loan.bank_id == bank_id)).scalar_one_or_none()
    if ln is None:
        raise HTTPException(status_code=404, detail="loan_not_found")

    s.delete(ln)
    s.commit()

    log_event(
        s,
        username=u.get("sub"),
        action="loan.delete",
        entity_type="loan",
        entity_id=loan_id,
        details={"bank_id": bank_id, "name": ln.name},
    )
    return {"ok": True}