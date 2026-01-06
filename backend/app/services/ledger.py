from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.transaction import Transaction
from app.models.bank import Bank
from app.models.rate import Rate
from app.services.bank_settings import get_settings_for_year

Q2 = Decimal("0.01")


def d2(x: Decimal) -> Decimal:
    return x.quantize(Q2, rounding=ROUND_HALF_UP)


def _to_dec(x) -> Decimal:
    return Decimal(str(x))


def _borrow_date(txs: list[Transaction]) -> date | None:
    ds = [t.date for t in txs if t.category == "principal" and _to_dec(t.amount) > Decimal("0")]
    return min(ds) if ds else None


def _prefetch_rates(s: Session, bank_id: int, end: date) -> dict[int, list[Rate]]:
    rows = (
        s.execute(
            select(Rate)
            .where(Rate.bank_id == bank_id, Rate.effective_date <= end)
            .order_by(Rate.tenor_months.asc(), Rate.effective_date.asc(), Rate.id.asc())
        )
        .scalars()
        .all()
    )

    by_tenor: dict[int, list[Rate]] = {}
    for r in rows:
        by_tenor.setdefault(int(r.tenor_months), []).append(r)
    return by_tenor


def _latest_rate_percent_for_day(
    by_tenor: dict[int, list[Rate]],
    tenor_months: int,
    day: date,
    fallback_percent: Decimal,
) -> Decimal:
    rs = by_tenor.get(int(tenor_months)) or []
    if not rs:
        return fallback_percent

    for r in reversed(rs):
        if r.effective_date <= day:
            return _to_dec(r.annual_rate_percent)
    return fallback_percent


def compute_ledger(s: Session, bank_id: int, start: date, end: date):
    bank = s.execute(select(Bank).where(Bank.id == bank_id)).scalar_one_or_none()
    if not bank:
        return []

    txs = (
        s.execute(
            select(Transaction)
            .where(
                Transaction.bank_id == bank_id,
                Transaction.date <= end,
            )
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

    prefetched_rates: dict[int, list[Rate]] | None = None
    if bank.bank_type != "islamic":
        prefetched_rates = _prefetch_rates(s, bank_id, end)

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
                addl = _to_dec(st.additional_rate) if st.additional_rate is not None else Decimal("0")
                placeholder = _to_dec(st.kibor_placeholder_rate_percent)

                base = _latest_rate_percent_for_day(
                    prefetched_rates or {},
                    int(st.kibor_tenor_months),
                    day,
                    placeholder,
                )
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