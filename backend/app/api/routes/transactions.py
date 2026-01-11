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

    ph_f: float | None = None
    if loan.kibor_placeholder_rate_percent is not None:
        ph = float(loan.kibor_placeholder_rate_percent)
        ph_f = ph if ph > 0 else None

    bank_type = (bank.bank_type or "").strip().lower()

    if bank_type == "islamic":
        max_day = max(t.date for t in txs)
        rate_rows = (
            s.execute(
                select(Rate.effective_date, Rate.annual_rate_percent)
                .where(
                    Rate.bank_id == bank.id,
                    Rate.tenor_months == tenor,
                    Rate.effective_date <= max_day,
                )
                .order_by(Rate.effective_date.asc())
            )
            .all()
        )
        rates: list[tuple[date, float]] = [(d, float(r)) for (d, r) in rate_rows]

        def latest_rate_on(day: date) -> float | None:
            latest: float | None = None
            for d, r in rates:
                if d <= day:
                    latest = r
                else:
                    break
            return latest if latest is not None else ph_f

        out: list[TxOut] = []
        for t in txs:
            rp: float | None = None
            if t.category == "principal" and float(t.amount) > 0:
                rp = latest_rate_on(t.date)
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

    max_day = max(t.date for t in txs)
    rate_rows = (
        s.execute(
            select(Rate.effective_date, Rate.annual_rate_percent)
            .where(
                Rate.bank_id == bank.id,
                Rate.tenor_months == tenor,
                Rate.effective_date <= max_day,
            )
            .order_by(Rate.effective_date.asc())
        )
        .all()
    )
    rates: list[tuple[date, float]] = [(d, float(r)) for (d, r) in rate_rows]

    def latest_rate_on(day: date) -> float | None:
        latest: float | None = None
        for d, r in rates:
            if d <= day:
                latest = r
            else:
                break
        return latest if latest is not None else ph_f

    out: list[TxOut] = []
    for t in txs:
        rp: float | None = None
        if t.category == "principal" and float(t.amount) > 0:
            rp = latest_rate_on(t.date)
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
        bank_type = (bank.bank_type or "").strip().lower()

        if bank_type == "islamic":
            anchor = t.date
            fetch_day = adjust_to_last_business_day(anchor)
            kib = get_kibor_offer_rates(fetch_day)
            offer = kib.by_tenor_months().get(int(loan.kibor_tenor_months))

            if offer is not None:
                stmt = (
                    pg_insert(Rate)
                    .values(
                        {
                            "bank_id": bank_id,
                            "tenor_months": int(loan.kibor_tenor_months),
                            "effective_date": anchor,
                            "annual_rate_percent": offer,
                        }
                    )
                    .on_conflict_do_nothing(index_elements=["bank_id", "tenor_months", "effective_date"])
                )
                s.execute(stmt)

                ph = float(loan.kibor_placeholder_rate_percent) if loan.kibor_placeholder_rate_percent is not None else 0.0
                if ph <= 0:
                    loan.kibor_placeholder_rate_percent = float(offer)
                    s.add(loan)

                s.commit()

        else:
            anchor = t.date
            fetch_day = adjust_to_last_business_day(anchor)
            kib = get_kibor_offer_rates(fetch_day)
            offer = kib.by_tenor_months().get(int(loan.kibor_tenor_months))

            if offer is not None:
                stmt = (
                    pg_insert(Rate)
                    .values(
                        {
                            "bank_id": bank_id,
                            "tenor_months": int(loan.kibor_tenor_months),
                            "effective_date": anchor,
                            "annual_rate_percent": offer,
                        }
                    )
                    .on_conflict_do_nothing(index_elements=["bank_id", "tenor_months", "effective_date"])
                )
                s.execute(stmt)

                ph = float(loan.kibor_placeholder_rate_percent) if loan.kibor_placeholder_rate_percent is not None else 0.0
                if ph <= 0:
                    loan.kibor_placeholder_rate_percent = float(offer)
                    s.add(loan)

                s.commit()

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