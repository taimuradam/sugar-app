from fastapi import APIRouter, Depends, Query, HTTPException
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.api.deps import db, current_user, require_admin
from app.schemas.transaction import TxCreate, TxOut
from app.models.transaction import Transaction
from app.models.bank import Bank
from app.models.loan import Loan
from app.models.rate import Rate
from app.services.audit import log_event
from app.services.kibor import get_kibor_offer_rates, adjust_to_last_business_day
from app.services.kibor_backfill import ensure_started

router = APIRouter(prefix="/banks/{bank_id}/loans/{loan_id}/transactions", tags=["transactions"])


def _require_bank_loan(s: Session, bank_id: int, loan_id: int) -> tuple[Bank, Loan]:
    b = s.execute(select(Bank).where(Bank.id == bank_id)).scalar_one_or_none()
    if b is None:
        raise HTTPException(status_code=404, detail="bank_not_found")
    ln = s.execute(select(Loan).where(Loan.id == loan_id, Loan.bank_id == bank_id)).scalar_one_or_none()
    if ln is None:
        raise HTTPException(status_code=404, detail="loan_not_found")
    return b, ln

def _attach_kibor_rates(
    s: Session,
    bank: Bank,
    loan: Loan,
    txs: list[Transaction],
) -> list[TxOut]:
    if not txs:
        return []

    tenor = int(loan.kibor_tenor_months)

    # Islamic banks: fixed at the first stored rate for this bank+tenor.
    if (bank.bank_type or "").strip().lower() == "islamic":
        fixed = (
            s.execute(
                select(Rate.annual_rate_percent)
                .where(Rate.bank_id == bank.id, Rate.tenor_months == tenor)
                .order_by(Rate.effective_date.asc())
                .limit(1)
            )
            .scalar_one_or_none()
        )
        fixed_f = float(fixed) if fixed is not None else None
        if fixed_f is None and loan.kibor_placeholder_rate_percent is not None:
            ph = float(loan.kibor_placeholder_rate_percent)
            fixed_f = ph if ph > 0 else None

        return [
            TxOut(
                id=t.id,
                bank_id=t.bank_id,
                loan_id=t.loan_id,
                date=t.date,
                category=t.category,
                amount=float(t.amount),
                kibor_rate_percent=fixed_f,
                note=t.note,
                created_at=t.created_at,
            )
            for t in txs
        ]

    # Conventional banks: rate is determined by the KIBOR table for the tx's business day.
    eff_dates = sorted({adjust_to_last_business_day(t.date) for t in txs})
    rate_rows = s.execute(
        select(Rate.effective_date, Rate.annual_rate_percent).where(
            Rate.bank_id == bank.id,
            Rate.tenor_months == tenor,
            Rate.effective_date.in_(eff_dates),
        )
    ).all()
    rate_map: dict[date, float] = {d: float(r) for (d, r) in rate_rows}

    ph_f: float | None = None
    if loan.kibor_placeholder_rate_percent is not None:
        ph = float(loan.kibor_placeholder_rate_percent)
        ph_f = ph if ph > 0 else None

    out: list[TxOut] = []
    for t in txs:
        eff = adjust_to_last_business_day(t.date)
        rp = rate_map.get(eff, ph_f)
        out.append(
            TxOut(
                id=t.id,
                bank_id=t.bank_id,
                loan_id=t.loan_id,
                date=t.date,
                category=t.category,
                amount=float(t.amount),
                kibor_rate_percent=rp,
                note=t.note,
                created_at=t.created_at,
            )
        )
    return out

@router.get("", response_model=list[TxOut])
def list_transactions(
    bank_id: int,
    loan_id: int,
    start: date | None = Query(None),
    end: date | None = Query(None),
    s: Session = Depends(db),
    u=Depends(current_user),
):
    bank, loan = _require_bank_loan(s, bank_id, loan_id)
    q = select(Transaction).where(Transaction.bank_id == bank_id, Transaction.loan_id == loan_id)
    if start is not None:
        q = q.where(Transaction.date >= start)
    if end is not None:
        q = q.where(Transaction.date <= end)
    q = q.order_by(Transaction.date.desc(), Transaction.id.desc())
    txs = s.execute(q).scalars().all()
    return _attach_kibor_rates(s, bank, loan, txs)


@router.post("", response_model=TxOut)
def add_tx(bank_id: int, loan_id: int, body: TxCreate, s: Session = Depends(db), u=Depends(require_admin)):
    bank, loan = _require_bank_loan(s, bank_id, loan_id)

    if body.category == "principal" and body.amount > 0 and loan.max_loan_amount is not None:
        current_principal = (
            s.execute(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                    Transaction.bank_id == bank_id,
                    Transaction.loan_id == loan_id,
                    Transaction.category == "principal",
                )
            )
            .scalar_one()
        )
        if float(current_principal) + float(body.amount) > float(loan.max_loan_amount):
            raise HTTPException(status_code=400, detail="max_loan_exceeded")

    t = Transaction(
        bank_id=bank_id,
        loan_id=loan_id,
        date=body.date,
        category=body.category,
        amount=body.amount,
        note=body.note,
    )
    s.add(t)
    s.commit()
    s.refresh(t)

    if t.category == "principal" and float(t.amount) > 0:
        borrow_date = (
            s.execute(
                select(func.min(Transaction.date)).where(
                    Transaction.bank_id == bank_id,
                    Transaction.loan_id == loan_id,
                    Transaction.category == "principal",
                    Transaction.amount > 0,
                )
            )
            .scalar_one()
        )

        if borrow_date == t.date:
            bd = adjust_to_last_business_day(t.date)
            kib = get_kibor_offer_rates(bd)
            offer = kib.by_tenor_months().get(int(loan.kibor_tenor_months))
            if offer is not None:
                stmt = (
                    pg_insert(Rate)
                    .values({"bank_id": bank_id, "tenor_months": int(loan.kibor_tenor_months), "effective_date": bd, "annual_rate_percent": offer})
                    .on_conflict_do_nothing(index_elements=["bank_id", "tenor_months", "effective_date"])
                )
                s.execute(stmt)
                loan.kibor_placeholder_rate_percent = float(offer)
                s.add(loan)
                s.commit()

        if bank.bank_type != "islamic":
            ensure_started(bank_id, loan_id)

    log_event(
        s,
        username=u.get("sub"),
        action="tx.create",
        entity_type="transaction",
        entity_id=t.id,
        details={"bank_id": bank_id, "loan_id": loan_id, "date": str(t.date), "category": t.category, "amount": str(t.amount), "note": t.note},
    )

    return _attach_kibor_rates(s, bank, loan, [t])[0]


@router.delete("/{tx_id}")
def delete_tx(bank_id: int, loan_id: int, tx_id: int, s: Session = Depends(db), u=Depends(require_admin)):
    _require_bank_loan(s, bank_id, loan_id)
    t = s.execute(select(Transaction).where(Transaction.id == tx_id, Transaction.bank_id == bank_id, Transaction.loan_id == loan_id)).scalar_one_or_none()
    if t is None:
        raise HTTPException(status_code=404, detail="tx_not_found")
    s.delete(t)
    s.commit()
    log_event(
        s,
        username=u.get("sub"),
        action="tx.delete",
        entity_type="transaction",
        entity_id=tx_id,
        details={"bank_id": bank_id, "loan_id": loan_id, "date": str(t.date), "category": t.category, "amount": str(t.amount)},
    )
    return {"ok": True}