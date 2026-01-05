from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.transaction import Transaction
from app.models.bank import Bank
from app.services.bank_settings import get_settings_for_year

Q2 = Decimal("0.01")

def d2(x: Decimal) -> Decimal:
    return x.quantize(Q2, rounding=ROUND_HALF_UP)

def _to_dec(x) -> Decimal:
    return Decimal(str(x))

def _borrow_date(txs: list[Transaction]) -> date | None:
    ds = [t.date for t in txs if t.category == "principal" and _to_dec(t.amount) > Decimal("0")]
    return min(ds) if ds else None

def compute_ledger(s: Session, bank_id: int, start: date, end: date):
    bank = s.execute(select(Bank).where(Bank.id == bank_id)).scalar_one_or_none()
    if not bank:
        return []

    txs = s.execute(
        select(Transaction).where(
            Transaction.bank_id == bank_id,
            Transaction.date <= end,
        ).order_by(Transaction.date.asc(), Transaction.id.asc())
    ).scalars().all()

    tx_by_day: dict[date, list[Transaction]] = {}
    for t in txs:
        tx_by_day.setdefault(t.date, []).append(t)

    calc_start = start
    if txs and txs[0].date < calc_start:
        calc_start = txs[0].date

    bd = _borrow_date(txs)

    principal = Decimal("0")
    accrued = Decimal("0")

    rows: list[dict] = []
    day = calc_start

    locked_rate: Decimal | None = None
    if bank.bank_type == "islamic" and bd is not None:
        st0 = get_settings_for_year(s, bank_id, bd.year)
        if st0:
            base = _to_dec(st0.kibor_placeholder_rate_percent)
            addl = _to_dec(st0.additional_rate) if st0.additional_rate is not None else Decimal("0")
            locked_rate = base + addl

    while day <= end:
        for t in tx_by_day.get(day, []):
            amt = _to_dec(t.amount)
            if t.category == "principal":
                principal = principal + amt
            elif t.category == "markup":
                accrued = accrued + amt

        if accrued < Decimal("0"):
            accrued = Decimal("0")

        current_rate = Decimal("0")
        if bank.bank_type == "islamic":
            current_rate = locked_rate if locked_rate is not None else Decimal("0")
        else:
            st = get_settings_for_year(s, bank_id, day.year)
            if st:
                base = _to_dec(st.kibor_placeholder_rate_percent)
                addl = _to_dec(st.additional_rate) if st.additional_rate is not None else Decimal("0")
                current_rate = base + addl

        daily_rate = (current_rate / Decimal("100")) / Decimal("365")
        daily_markup = d2(principal * daily_rate)
        accrued = d2(accrued + daily_markup)

        if day >= start:
            rows.append({
                "date": day,
                "principal_balance": float(d2(principal)),
                "daily_markup": float(daily_markup),
                "accrued_markup": float(accrued),
                "rate_percent": float(current_rate),
            })

        day = day + timedelta(days=1)

    return rows