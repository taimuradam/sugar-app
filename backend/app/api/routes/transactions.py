from fastapi import APIRouter, Depends, Query
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.api.deps import db, current_user
from app.schemas.transaction import TxCreate, TxOut
from app.models.transaction import Transaction

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
    return t
