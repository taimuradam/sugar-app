from fastapi import APIRouter, Depends, Query, HTTPException
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.api.deps import db, current_user, require_admin
from app.schemas.transaction import TxCreate, TxOut
from app.models.transaction import Transaction
from app.services.audit import log_event
from app.services.bank_settings import get_settings_for_year
from app.models.bank import Bank
from app.models.rate import Rate
from app.services.kibor import get_kibor_offer_rates, adjust_to_last_business_day
from app.services.kibor_backfill import ensure_started

router = APIRouter(prefix="/banks/{bank_id}/transactions", tags=["transactions"])


def _is_islamic(bank_type: str) -> bool:
    return (bank_type or "").strip().lower() == "islamic"


@router.get("", response_model=list[TxOut])
def list_txs(
    bank_id: int,
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    s: Session = Depends(db),
    u=Depends(current_user),
):
    q = select(Transaction).where(Transaction.bank_id == bank_id)
    if start:
        q = q.where(Transaction.date >= start)
    if end:
        q = q.where(Transaction.date <= end)
    q = q.order_by(Transaction.date.asc(), Transaction.id.asc())
    return s.execute(q).scalars().all()


@router.post("", response_model=TxOut)
def add_tx(bank_id: int, body: TxCreate, s: Session = Depends(db), u=Depends(require_admin)):
    if body.category == "principal" and body.amount > 0:
        st = get_settings_for_year(s, bank_id, body.date.year)
        if st and st.max_loan_amount is not None:
            current_principal = s.execute(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                    Transaction.bank_id == bank_id,
                    Transaction.category == "principal",
                )
            ).scalar_one()
            if float(current_principal) + float(body.amount) > float(st.max_loan_amount):
                raise HTTPException(status_code=400, detail="max_loan_exceeded")

    t = Transaction(bank_id=bank_id, date=body.date, category=body.category, amount=body.amount, note=body.note)
    s.add(t)
    s.commit()
    s.refresh(t)

    if t.category == "principal" and float(t.amount) > 0:
        borrow_date = (
            s.execute(
                select(func.min(Transaction.date)).where(
                    Transaction.bank_id == bank_id,
                    Transaction.category == "principal",
                    Transaction.amount > 0,
                )
            )
            .scalar_one()
        )

        bank = s.execute(select(Bank).where(Bank.id == bank_id)).scalar_one_or_none()

        if borrow_date is not None and t.date == borrow_date and bank is not None:
            st = get_settings_for_year(s, bank_id, borrow_date.year)
            if st is not None:
                rate_day = adjust_to_last_business_day(borrow_date)
                kib = get_kibor_offer_rates(rate_day)

                values = []
                for tenor_months, offer in kib.by_tenor_months().items():
                    values.append(
                        {
                            "bank_id": bank_id,
                            "tenor_months": int(tenor_months),
                            "effective_date": kib.effective_date,
                            "annual_rate_percent": offer,
                        }
                    )

                if values:
                    stmt = (
                        pg_insert(Rate)
                        .values(values)
                        .on_conflict_do_nothing(index_elements=["bank_id", "tenor_months", "effective_date"])
                    )
                    s.execute(stmt)

                base_for_tenor = float(kib.by_tenor_months().get(int(st.kibor_tenor_months), 0.0))
                st.kibor_placeholder_rate_percent = base_for_tenor
                s.add(st)
                s.commit()
        if bank is not None and not _is_islamic(bank.bank_type):
            ensure_started(bank_id)

    log_event(
        s,
        username=u.get("sub"),
        action="transaction.create",
        entity_type="transaction",
        entity_id=t.id,
        details={
            "bank_id": bank_id,
            "date": str(t.date),
            "category": t.category,
            "amount": str(t.amount),
            "note": t.note,
        },
    )

    return t