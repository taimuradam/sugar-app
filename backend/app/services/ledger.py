from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bank import Bank
from app.models.loan import Loan
from app.models.rate import Rate
from app.models.transaction import Transaction

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


def _latest_rate_percent_for_day(
    prefetched: dict[int, list[Rate]],
    tenor_months: int,
    day: date,
    placeholder: Decimal,
) -> Decimal:
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


def _month_start(d: date) -> date:
    return date(d.year, d.month, 1)


def _next_month_start(d: date) -> date:
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


@dataclass
class _Tranche:
    start_date: date
    amount: Decimal
    base_rate_percent: Decimal | None = None


def _apply_principal_tx(
    tranches: list[_Tranche],
    tx_date: date,
    amount: Decimal,
    base_rate_percent: Decimal | None = None,
) -> None:
    if amount == 0:
        return

    if amount > 0:
        tranches.append(_Tranche(start_date=tx_date, amount=amount, base_rate_percent=base_rate_percent))
        return

    repay = -amount
    tranches.sort(key=lambda t: t.start_date)
    i = 0
    while repay > 0 and i < len(tranches):
        t = tranches[i]
        if t.amount <= repay:
            repay -= t.amount
            t.amount = Decimal("0")
            i += 1
        else:
            t.amount -= repay
            repay = Decimal("0")

    tranches[:] = [t for t in tranches if t.amount > 0]


def _total_principal(tranches: list[_Tranche]) -> Decimal:
    return sum((t.amount for t in tranches), Decimal("0"))


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

    prefetched_rates = _prefetch_rates(s, bank_id, end)

    placeholder = _to_dec(loan.kibor_placeholder_rate_percent)
    tenor = int(loan.kibor_tenor_months)
    addl = _to_dec(loan.additional_rate) if loan.additional_rate is not None else Decimal("0")

    accrued = Decimal("0")
    tranches: list[_Tranche] = []

    month_rate_cache: dict[date, Decimal] = {}

    def _rate_for_month_start(ms: date) -> Decimal:
        v = month_rate_cache.get(ms)
        if v is None:
            v = _latest_rate_percent_for_day(prefetched_rates, tenor, ms, placeholder)
            month_rate_cache[ms] = v
        return v

    def tranche_rate_base_for_day(day: date, tr: _Tranche) -> Decimal:
        if bank.bank_type == "islamic":
            return _latest_rate_percent_for_day(prefetched_rates, tenor, tr.start_date, placeholder)

        if day < _next_month_start(tr.start_date):
            if tr.base_rate_percent is not None:
                return tr.base_rate_percent
            return _latest_rate_percent_for_day(prefetched_rates, tenor, tr.start_date, placeholder)

        return _rate_for_month_start(_month_start(day))

    rows: list[dict] = []
    day = calc_start
    while day <= end:
        for t in tx_by_day.get(day, []):
            amt = _to_dec(t.amount)
            if t.category == "principal":
                base_rate = None
                if bank.bank_type != "islamic" and amt > 0:
                    base_rate = _latest_rate_percent_for_day(prefetched_rates, tenor, t.date, placeholder)
                _apply_principal_tx(tranches, t.date, amt, base_rate_percent=base_rate)
            elif t.category == "markup":
                accrued += amt

        weighted_daily_markup = Decimal("0")
        for tr in tranches:
            base = tranche_rate_base_for_day(day, tr)
            rate_percent = base + addl
            daily_rate = (rate_percent / Decimal("100")) / Decimal("365")
            weighted_daily_markup += tr.amount * daily_rate

        daily_markup = weighted_daily_markup
        accrued = accrued + daily_markup

        if accrued < Decimal("0"):
            accrued = Decimal("0")

        if day >= start:
            principal_total = _total_principal(tranches)

            if principal_total > 0:
                weighted_rate = (
                    sum(
                        (tr.amount * (tranche_rate_base_for_day(day, tr) + addl) for tr in tranches),
                        Decimal("0"),
                    )
                    / principal_total
                )
            else:
                weighted_rate = Decimal("0")

            rows.append(
                {
                    "date": day,
                    "principal_balance": float(d2(principal_total)),
                    "daily_markup": float(daily_markup),
                    "accrued_markup": float(accrued),
                    "rate_percent": float(weighted_rate),
                }
            )

        day = day + timedelta(days=1)

    return rows
