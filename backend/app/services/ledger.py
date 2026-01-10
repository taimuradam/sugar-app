from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.transaction import Transaction
from app.models.bank import Bank
from app.models.loan import Loan
from app.models.rate import Rate

Q2 = Decimal("0.01")

def d2(x: Decimal) -> Decimal:
    return x.quantize(Q2, rounding=ROUND_HALF_UP)

def _to_dec(v) -> Decimal:
    return Decimal(str(v))

def _prefetch_rates(s: Session, bank_id: int, end: date) -> dict[int, list[Rate]]:
    rows = (
        s.execute(
            select(Rate)
            .where(Rate.bank_id == bank_id, Rate.effective_date <= end)
            .order_by(Rate.tenor_months.asc(), Rate.effective_date.asc())
        )
        .scalars()
        .all()
    )
    out: dict[int, list[Rate]] = {}
    for r in rows:
        out.setdefault(int(r.tenor_months), []).append(r)
    return out

def _latest_rate_percent_for_day(prefetched: dict[int, list[Rate]], tenor_months: int, day: date, placeholder: Decimal) -> Decimal:
    rs = prefetched.get(int(tenor_months), [])
    latest: Rate | None = None
    for r in rs:
        if r.effective_date <= day:
            latest = r
        else:
            break
    if latest is None:
        return placeholder
    return _to_dec(latest.annual_rate_percent)

def compute_ledger(s: Session, bank_id: int, loan_id: int, start: date, end: date):
    bank = s.execute(select(Bank).where(Bank.id == bank_id)).scalar_one()
    loan = s.execute(select(Loan).where(Loan.id == loan_id, Loan.bank_id == bank_id)).scalar_one()

    txs = (
        s.execute(
            select(Transaction)
            .where(Transaction.bank_id == bank_id, Transaction.loan_id == loan_id, Transaction.date <= end)
            .order_by(Transaction.date.asc(), Transaction.id.asc())
        )
        .scalars()
        .all()
    )

    tx_by_day: dict[date, list[Transaction]] = {}
    for t in txs:
        tx_by_day.setdefault(t.date, []).append(t)

    calc_start = start
    if txs and txs[0].date < calc_start:
        calc_start = txs[0].date

    bd = None
    for t in txs:
        if t.category == "principal" and float(t.amount) > 0:
            bd = t.date
            break

    principal = Decimal("0")
    accrued = Decimal("0")

    prefetched_rates = _prefetch_rates(s, bank_id, end)

    locked_rate: Decimal | None = None
    if bank.bank_type == "islamic" and bd is not None:
        placeholder = _to_dec(loan.kibor_placeholder_rate_percent)
        locked_base = _latest_rate_percent_for_day(prefetched_rates, int(loan.kibor_tenor_months), bd, placeholder)
        addl = _to_dec(loan.additional_rate) if loan.additional_rate is not None else Decimal("0")
        locked_rate = locked_base + addl

    day = calc_start
    rows: list[dict] = []
    while day <= end:
        for t in tx_by_day.get(day, []):
            amt = _to_dec(t.amount)
            if t.category == "principal":
                principal = principal + amt
            elif t.category == "markup":
                accrued = accrued + amt

        if accrued < Decimal("0"):
            accrued = Decimal("0")

        if bank.bank_type == "islamic":
            current_rate = locked_rate if locked_rate is not None else Decimal("0")
        else:
            addl = _to_dec(loan.additional_rate) if loan.additional_rate is not None else Decimal("0")
            placeholder = _to_dec(loan.kibor_placeholder_rate_percent)
            base = _latest_rate_percent_for_day(prefetched_rates, int(loan.kibor_tenor_months), day, placeholder)
            current_rate = base + addl

        daily_rate = (current_rate / Decimal("100")) / Decimal("365")
        daily_markup = d2(principal * daily_rate)
        accrued = d2(accrued + daily_markup)

        if day >= start:
            rows.append(
                {
                    "date": day,
                    "principal_balance": float(d2(principal)),
                    "daily_markup": float(daily_markup),
                    "accrued_markup": float(accrued),
                    "rate_percent": float(current_rate),
                }
            )

        day = day + timedelta(days=1)

    return rows