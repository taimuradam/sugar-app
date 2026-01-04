from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.transaction import Transaction
from app.models.rate import Rate
from app.models.bank import Bank

Q2 = Decimal("0.01")


def d2(x: Decimal) -> Decimal:
    return x.quantize(Q2, rounding=ROUND_HALF_UP)


def _to_dec(x) -> Decimal:
    return Decimal(str(x))


def compute_ledger(s: Session, bank_id: int, start: date, end: date):
    bank = s.execute(select(Bank).where(Bank.id == bank_id)).scalar_one_or_none()
    addl = _to_dec(bank.additional_rate) if (bank and bank.additional_rate is not None) else Decimal("0")

    # IMPORTANT FIX:
    # Load ALL transactions up to `end`, so we can compute correct opening balances at `start`.
    txs = s.execute(
        select(Transaction).where(
            Transaction.bank_id == bank_id,
            Transaction.date <= end,
        ).order_by(Transaction.date.asc(), Transaction.id.asc())
    ).scalars().all()

    rates = s.execute(
        select(Rate).where(Rate.bank_id == bank_id).order_by(Rate.effective_date.asc(), Rate.id.asc())
    ).scalars().all()

    tx_by_day: dict[date, list[Transaction]] = {}
    for t in txs:
        tx_by_day.setdefault(t.date, []).append(t)

    # Start computing from earliest transaction date if it is before `start`
    calc_start = start
    if txs and txs[0].date < calc_start:
        calc_start = txs[0].date

    # Better rate handling:
    # - If there is no rate effective yet for a day, base_rate = 0.
    rate_idx = -1
    base_rate = Decimal("0")
    current_rate = base_rate + addl

    principal = Decimal("0")
    accrued = Decimal("0")

    rows: list[dict] = []
    day = calc_start
    while day <= end:
        while rate_idx + 1 < len(rates) and rates[rate_idx + 1].effective_date <= day:
            rate_idx += 1
            base_rate = _to_dec(rates[rate_idx].annual_rate_percent)
            current_rate = base_rate + addl

        for t in tx_by_day.get(day, []):
            amt = _to_dec(t.amount)
            if t.category == "principal":
                principal = principal + amt
            elif t.category == "markup":
                accrued = accrued + amt

        if accrued < Decimal("0"):
            accrued = Decimal("0")

        daily_rate = (current_rate / Decimal("100")) / Decimal("365")
        daily_markup = d2(principal * daily_rate)
        accrued = d2(accrued + daily_markup)

        # Only RETURN rows in the requested range
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
