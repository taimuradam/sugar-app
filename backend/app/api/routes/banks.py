from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.api.deps import db, current_user, require_admin
from app.schemas.bank import BankCreate, BankOut
from app.models.bank import Bank

router = APIRouter(prefix="/banks", tags=["banks"])

@router.get("", response_model=list[BankOut])
def list_banks(s: Session = Depends(db), u=Depends(current_user)):
    return s.execute(select(Bank).order_by(Bank.name.asc())).scalars().all()

@router.post("", response_model=BankOut)
def create_bank(body: BankCreate, s: Session = Depends(db), u=Depends(require_admin)):
    exists = s.execute(select(Bank).where(Bank.name == body.name)).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="bank_exists")
    b = Bank(name=body.name, bank_type=body.bank_type, additional_rate=body.additional_rate)
    s.add(b)
    s.commit()
    s.refresh(b)
    return b
