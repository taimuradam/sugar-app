from __future__ import annotations

import threading
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
from typing import Dict, Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.bank import Bank
from app.models.loan import Loan
from app.models.rate import Rate
from app.models.transaction import Transaction
from app.services.kibor import get_kibor_offer_rates, adjust_to_last_business_day
from app.utils.timezone import today_karachi

@dataclass
class _Status:
    status: str = "idle"  # idle | running | done | error
    total_days: int = 0
    processed_days: int = 0
    started_at: str | None = None
    message: str | None = None


_lock = threading.Lock()
_status: Dict[str, _Status] = {}


def _key(bank_id: int, loan_id: int) -> str:
    return f"{bank_id}:{loan_id}"


def _iso_now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def get_status(bank_id: int, loan_id: int) -> Dict[str, Any]:
    k = _key(bank_id, loan_id)
    with _lock:
        st = _status.get(k) or _Status()
        _status[k] = st
        return asdict(st)


def _set_status(bank_id: int, loan_id: int, **updates):
    k = _key(bank_id, loan_id)
    with _lock:
        st = _status.get(k) or _Status()
        for kk, vv in updates.items():
            setattr(st, kk, vv)
        _status[k] = st


def _month_start(d: date) -> date:
    return date(d.year, d.month, 1)


def _add_months(d: date, months: int) -> date:
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    return date(y, m, 1)


def _iter_month_starts(start: date, end: date):
    cur = _month_start(start)
    last = _month_start(end)
    while cur <= last:
        yield cur
        cur = _add_months(cur, 1)


def _compute_missing_days(s: Session, bank_id: int, loan_id: int) -> list[date]:
    bank = s.execute(select(Bank).where(Bank.id == bank_id)).scalar_one_or_none()
    loan = s.execute(select(Loan).where(Loan.id == loan_id, Loan.bank_id == bank_id)).scalar_one_or_none()
    if bank is None or loan is None:
        return []

    principal_dates = (
        s.execute(
            select(Transaction.date)
            .where(
                Transaction.bank_id == bank_id,
                Transaction.loan_id == loan_id,
                Transaction.category == "principal",
                Transaction.amount > 0,
            )
            .distinct()
        )
        .scalars()
        .all()
    )
    if not principal_dates:
        return []

    earliest = min(principal_dates)
    today = today_karachi()

    anchor_dates: set[date] = set(principal_dates)

    if bank.bank_type != "islamic":
        for ms in _iter_month_starts(earliest, today):
            anchor_dates.add(ms)

    tenor = int(loan.kibor_tenor_months)

    existing = (
        s.execute(
            select(Rate.effective_date).where(
                Rate.bank_id == bank_id,
                Rate.tenor_months == tenor,
                Rate.effective_date.in_(sorted(anchor_dates)),
            )
        )
        .scalars()
        .all()
    )
    have = set(existing)

    return sorted(anchor_dates - have)


def _run_job(bank_id: int, loan_id: int):
    s = SessionLocal()
    try:
        loan = s.execute(select(Loan).where(Loan.id == loan_id, Loan.bank_id == bank_id)).scalar_one()
        tenor = int(loan.kibor_tenor_months)

        missing = _compute_missing_days(s, bank_id, loan_id)
        if not missing:
            _set_status(bank_id, loan_id, status="done", total_days=0, processed_days=0, started_at=None, message=None)
            return

        processed = 0
        for d in missing:
            try:
                fetch_day = adjust_to_last_business_day(d)
                kib = get_kibor_offer_rates(fetch_day)
                offer = kib.by_tenor_months().get(tenor)
                if offer is not None:
                    stmt = (
                        pg_insert(Rate)
                        .values(
                            {
                                "bank_id": bank_id,
                                "tenor_months": tenor,
                                "effective_date": d,  # IMPORTANT: store the ANCHOR date (tx date / month-start)
                                "annual_rate_percent": offer,
                            }
                        )
                        .on_conflict_do_nothing(index_elements=["bank_id", "tenor_months", "effective_date"])
                    )
                    s.execute(stmt)
                    s.commit()
            except Exception:
                s.rollback()

            processed += 1
            _set_status(bank_id, loan_id, processed_days=processed)
    except Exception as e:
        _set_status(bank_id, loan_id, status="error", message=str(e))
    finally:
        s.close()
        st = get_status(bank_id, loan_id)
        if st.get("status") != "error":
            _set_status(bank_id, loan_id, status="done", message=None, started_at=None)


def ensure_started(bank_id: int, loan_id: int) -> Dict[str, Any]:
    st = get_status(bank_id, loan_id)
    if st.get("status") == "running":
        return st

    s = SessionLocal()
    try:
        missing = _compute_missing_days(s, bank_id, loan_id)
    finally:
        s.close()

    if not missing:
        _set_status(bank_id, loan_id, status="done", total_days=0, processed_days=0, started_at=None, message=None)
        return get_status(bank_id, loan_id)

    _set_status(
        bank_id,
        loan_id,
        status="running",
        total_days=len(missing),
        processed_days=0,
        started_at=_iso_now(),
        message=None,
    )
    t = threading.Thread(target=_run_job, args=(bank_id, loan_id), daemon=True)
    t.start()
    return get_status(bank_id, loan_id)


def is_ready(s: Session, bank_id: int, loan_id: int) -> bool:
    return len(_compute_missing_days(s, bank_id, loan_id)) == 0