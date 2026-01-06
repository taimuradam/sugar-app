from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from datetime import date
from app.api.deps import db, current_user, require_admin
from app.schemas.bank import BankCreate, BankOut
from app.models.bank import Bank
from app.models.bank_settings import BankSettings
from app.models.transaction import Transaction
from app.services.audit import log_event
from app.services.bank_settings import resolve_year
from app.models.rate import Rate
from app.services.kibor import get_kibor_offer_rates, adjust_to_last_business_day
from app.services.kibor_sync import maybe_refresh_kibor_rates

router = APIRouter(prefix="/banks", tags=["banks"])

def _is_islamic(bank_type: str) -> bool:
    return (bank_type or "").strip().lower() == "islamic"


def _ensure_latest_kibor_rates_for_bank(s: Session, bank_id: int, target_day: date) -> None:
    kib = get_kibor_offer_rates(target_day)
    rates = kib.by_tenor_months()

    for tenor_months, offer in rates.items():
        existing = (
            s.execute(
                select(Rate).where(
                    Rate.bank_id == bank_id,
                    Rate.tenor_months == int(tenor_months),
                    Rate.effective_date == kib.effective_date,
                )
            )
            .scalars()
            .first()
        )

        if existing:
            if float(existing.annual_rate_percent) != float(offer):
                existing.annual_rate_percent = offer
                s.add(existing)
        else:
            s.add(
                Rate(
                    bank_id=bank_id,
                    tenor_months=int(tenor_months),
                    effective_date=kib.effective_date,
                    annual_rate_percent=offer,
                )
            )

def _bank_out(s: Session, b: Bank, st: BankSettings) -> dict:
    principal_sum = s.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .where(
            Transaction.bank_id == b.id,
            Transaction.category == "principal",
        )
    ).scalar_one()

    principal_balance = float(principal_sum or 0)

    max_loan = float(st.max_loan_amount) if st.max_loan_amount is not None else None
    remaining = None
    util = None
    if max_loan is not None:
        used = principal_balance if principal_balance > 0 else 0.0
        remaining = max_loan - used
        if remaining < 0:
            remaining = 0.0
        util = (used / max_loan * 100.0) if max_loan > 0 else 0.0

        if not _is_islamic(b.bank_type):
            target_day = adjust_to_last_business_day(date.today())

            if st.kibor_tenor_months is not None:
                latest = (
                    s.execute(
                        select(func.max(Rate.effective_date)).where(
                            Rate.bank_id == b.id,
                            Rate.tenor_months == st.kibor_tenor_months,
                        )
                    )
                    .scalar_one()
                )
            else:
                latest = None

            if latest is None or latest < target_day:
                _ensure_latest_kibor_rates_for_bank(s, b.id, target_day)
                s.commit()

    today = date.today()
    current_rate = (
        s.execute(
            select(Rate)
            .where(
                Rate.bank_id == b.id,
                Rate.tenor_months == st.kibor_tenor_months,
                Rate.effective_date <= today,
            )
            .order_by(Rate.effective_date.desc(), Rate.created_at.desc(), Rate.id.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )

    current_kibor = float(current_rate.annual_rate_percent) if current_rate else None
    current_eff = current_rate.effective_date if current_rate else None

    addl = float(st.additional_rate) if st.additional_rate is not None else None
    current_total = (current_kibor + (addl or 0.0)) if current_kibor is not None else None

    return {
        "id": b.id,
        "name": b.name,
        "bank_type": b.bank_type,
        "created_at": b.created_at,
        "settings_year": st.year,
        "kibor_tenor_months": st.kibor_tenor_months,
        "additional_rate": float(st.additional_rate) if st.additional_rate is not None else None,
        "kibor_placeholder_rate_percent": float(st.kibor_placeholder_rate_percent),
        "max_loan_amount": max_loan,
        "principal_balance": principal_balance,
        "remaining_loan_amount": remaining,
        "loan_utilization_percent": util,
        "current_kibor_rate_percent": current_kibor,
        "current_kibor_effective_date": current_eff,
        "current_total_rate_percent": current_total,
    }

@router.get("", response_model=list[BankOut])
def list_banks(s: Session = Depends(db), u=Depends(current_user)):
    maybe_refresh_kibor_rates(s)
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

    creation_day = adjust_to_last_business_day(date.today())
    kib = get_kibor_offer_rates(creation_day)

    for tenor_months, offer in kib.by_tenor_months().items():
        s.add(
            Rate(
                bank_id=b.id,
                tenor_months=tenor_months,
                effective_date=kib.effective_date,
                annual_rate_percent=offer,
            )
        )

    st.kibor_placeholder_rate_percent = float(kib.by_tenor_months().get(int(st.kibor_tenor_months), 0.0))
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