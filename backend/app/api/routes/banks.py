from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import date
from app.models.rate import Rate
from app.api.deps import db, current_user, require_admin
from app.schemas.bank import BankCreate, BankOut
from app.models.bank import Bank
from app.models.bank_settings import BankSettings
from app.services.audit import log_event
from app.services.bank_settings import resolve_year

router = APIRouter(prefix="/banks", tags=["banks"])

def _bank_out(s: Session, b: Bank, st: BankSettings) -> dict:
    today = date.today()

    base_q = select(Rate).where(
        Rate.bank_id == b.id,
        Rate.tenor_months == st.kibor_tenor_months,
    )

    # 1) Prefer rate effective today or earlier
    current_rate = (
        s.execute(
            base_q
            .where(Rate.effective_date <= today)
            .order_by(
                Rate.effective_date.desc(),
                Rate.created_at.desc(),
                Rate.id.desc(),
            )
            .limit(1)
        )
        .scalars()
        .first()
    )

    # 2) If none exist (e.g. only future-dated rows), fall back to newest rate
    if not current_rate:
        current_rate = (
            s.execute(
                base_q
                .order_by(
                    Rate.effective_date.desc(),
                    Rate.created_at.desc(),
                    Rate.id.desc(),
                )
                .limit(1)
            )
            .scalars()
            .first()
        )

    current_kibor = float(current_rate.annual_rate_percent) if current_rate else None
    addl = float(st.additional_rate) if st.additional_rate is not None else 0.0
    current_total = (current_kibor + addl) if current_kibor is not None else None

    return {
        "id": b.id,
        "name": b.name,
        "bank_type": b.bank_type,
        "created_at": b.created_at,
        "settings_year": st.year,
        "kibor_tenor_months": st.kibor_tenor_months,
        "additional_rate": float(st.additional_rate) if st.additional_rate is not None else None,
        "kibor_placeholder_rate_percent": float(st.kibor_placeholder_rate_percent),
        "max_loan_amount": float(st.max_loan_amount) if st.max_loan_amount is not None else None,
        "current_kibor_rate_percent": current_kibor,
        "current_kibor_effective_date": current_rate.effective_date if current_rate else None,
        "current_total_rate_percent": current_total,
    }

@router.get("", response_model=list[BankOut])
def list_banks(s: Session = Depends(db), u=Depends(current_user)):
    banks = s.execute(select(Bank).order_by(Bank.name.asc())).scalars().all()
    out = []
    for b in banks:
        st = s.execute(
            select(BankSettings).where(BankSettings.bank_id == b.id).order_by(BankSettings.year.desc())
        ).scalars().first()
        if not st:
            st = BankSettings(
                bank_id=b.id,
                year=date.today().year,
                kibor_tenor_months=1,
                additional_rate=None,
                kibor_placeholder_rate_percent=0,
                max_loan_amount=None,
            )
            s.add(st)
            s.commit()
            s.refresh(st)
        out.append(_bank_out(s, b, st))
    return out

@router.post("", response_model=BankOut)
def create_bank(body: BankCreate, s: Session = Depends(db), u=Depends(require_admin)):
    nm = body.name.strip()
    if not nm:
        raise HTTPException(status_code=400, detail="bank_name_required")

    if body.kibor_tenor_months not in (1, 3, 6):
        raise HTTPException(status_code=400, detail="kibor_tenor_invalid")

    exists = s.execute(select(Bank).where(Bank.name == nm)).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="bank_exists")

    b = Bank(name=nm, bank_type=body.bank_type, additional_rate=None)
    s.add(b)
    s.commit()
    s.refresh(b)

    yr = resolve_year(body.year)

    st = BankSettings(
        bank_id=b.id,
        year=yr,
        kibor_tenor_months=body.kibor_tenor_months,
        additional_rate=body.additional_rate,
        kibor_placeholder_rate_percent=body.kibor_placeholder_rate_percent,
        max_loan_amount=body.max_loan_amount,
    )
    s.add(st)
    s.commit()
    s.refresh(st)

    log_event(
        s,
        username=u.get("sub"),
        action="bank.create",
        entity_type="bank",
        entity_id=b.id,
        details={
            "name": b.name,
            "bank_type": b.bank_type,
            "settings_year": st.year,
            "kibor_tenor_months": st.kibor_tenor_months,
            "additional_rate": str(st.additional_rate) if st.additional_rate is not None else None,
            "kibor_placeholder_rate_percent": str(st.kibor_placeholder_rate_percent),
            "max_loan_amount": str(st.max_loan_amount) if st.max_loan_amount is not None else None,
        },
    )

    return _bank_out(s, b, st)