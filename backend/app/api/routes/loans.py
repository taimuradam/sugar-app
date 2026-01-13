from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from datetime import datetime, date

from app.api.deps import db, current_user, require_admin
from app.models.bank import Bank
from app.models.loan import Loan
from app.models.transaction import Transaction
from app.schemas.loan import LoanCreate, LoanOut, LoanBalanceOut
from app.schemas.date_bounds import LoanDateBoundsOut
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
    if body.kibor_tenor_months not in (1, 3, 6, 9, 12):
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

@router.get("/{loan_id}/date-bounds", response_model=LoanDateBoundsOut)
def loan_date_bounds(bank_id: int, loan_id: int, s: Session = Depends(db), u=Depends(current_user)):
    _require_bank(s, bank_id)
    ln = s.execute(select(Loan).where(Loan.id == loan_id, Loan.bank_id == bank_id)).scalar_one_or_none()
    if ln is None:
        raise HTTPException(status_code=404, detail="loan_not_found")

    row = s.execute(
        select(func.min(Transaction.date), func.max(Transaction.date)).where(
            Transaction.bank_id == bank_id,
            Transaction.loan_id == loan_id,
        )
    ).one()

    return LoanDateBoundsOut(min_date=row[0], max_date=row[1])

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

@router.get("/{loan_id}/balance", response_model=LoanBalanceOut)
def loan_balance(bank_id: int, loan_id: int, s: Session = Depends(db), u=Depends(current_user)):
    _require_bank(s, bank_id)
    ln = s.execute(select(Loan).where(Loan.id == loan_id, Loan.bank_id == bank_id)).scalar_one_or_none()
    if ln is None:
        raise HTTPException(status_code=404, detail="loan_not_found")

    as_of = date.today()
    principal = (
        s.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.bank_id == bank_id,
                Transaction.loan_id == loan_id,
                Transaction.category == "principal",
                Transaction.date <= as_of,
            )
        )
        .scalar_one()
    )

    return LoanBalanceOut(
        bank_id=bank_id,
        loan_id=loan_id,
        principal_balance=float(principal),
        as_of=datetime.utcnow(),
    )