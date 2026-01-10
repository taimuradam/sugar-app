from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.api.deps import db, current_user, require_admin
from app.schemas.bank import BankCreate, BankOut
from app.models.bank import Bank
from app.services.audit import log_event

router = APIRouter(prefix="/banks", tags=["banks"])


@router.get("", response_model=list[BankOut])
def list_banks(s: Session = Depends(db), u=Depends(current_user)):
    return s.execute(select(Bank).order_by(Bank.name.asc())).scalars().all()


@router.post("", response_model=BankOut)
def create_bank(body: BankCreate, s: Session = Depends(db), u=Depends(require_admin)):
    nm = body.name.strip()
    if not nm:
        raise HTTPException(status_code=400, detail="bank_name_required")

    exists = s.execute(select(Bank).where(Bank.name == nm)).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="bank_exists")

    b = Bank(name=nm, bank_type=body.bank_type, additional_rate=None)
    s.add(b)
    s.commit()
    s.refresh(b)

    log_event(
        s,
        username=u.get("sub"),
        action="bank.create",
        entity_type="bank",
        entity_id=b.id,
        details={"name": b.name, "bank_type": b.bank_type},
    )

    return b


@router.delete("/{bank_id}")
def delete_bank(bank_id: int, s: Session = Depends(db), u=Depends(require_admin)):
    b = s.execute(select(Bank).where(Bank.id == bank_id)).scalar_one_or_none()
    if b is None:
        raise HTTPException(status_code=404, detail="bank_not_found")
    s.delete(b)
    s.commit()
    log_event(
        s,
        username=u.get("sub"),
        action="bank.delete",
        entity_type="bank",
        entity_id=bank_id,
        details={"name": b.name},
    )
    return {"ok": True}