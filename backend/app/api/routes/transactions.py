from fastapi import APIRouter, Depends, Query, HTTPException
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.api.deps import db, current_user, require_admin
from app.schemas.transaction import TxCreate, TxOut
from app.models.transaction import Transaction
from app.services.audit import log_event

router = APIRouter(prefix="/banks/{bank_id}/transactions", tags=["transactions"])

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
def add_tx(bank_id: int, body: TxCreate, s: Session = Depends(db), u=Depends(current_user)):
    t = Transaction(bank_id=bank_id, date=body.date, category=body.category, amount=body.amount, note=body.note)
    s.add(t)
    s.commit()
    s.refresh(t)

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

@router.delete("/{tx_id}")
def delete_tx(bank_id: int, tx_id: int, s: Session = Depends(db), u=Depends(require_admin)):
    t = s.execute(select(Transaction).where(Transaction.id == tx_id, Transaction.bank_id == bank_id)).scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="tx_not_found")
    
    details = {
        "bank_id": bank_id,
        "date": str(t.date),
        "category": t.category,
        "amount": str(t.amount),
        "note": t.note,
    }
    s.delete(t)
    s.commit()

    log_event(
        s,
        username=u.get("sub"),
        action="transaction.delete",
        entity_type="transaction",
        entity_id=tx_id,
        details=details,
    )
    return {"ok": True}