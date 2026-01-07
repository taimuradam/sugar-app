from __future__ import annotations

import threading
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
from typing import Optional, Dict, Any

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.bank import Bank
from app.models.rate import Rate
from app.models.transaction import Transaction
from app.services.kibor import get_kibor_offer_rates, adjust_to_last_business_day


def _is_business_day(d: date) -> bool:
    return d.weekday() < 5


def _is_islamic(bank_type: str) -> bool:
    bt = (bank_type or "").strip().lower()
    return "islamic" in bt or "islam" in bt


def _iso_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


@dataclass
class _Job:
    status: str = "idle"  # idle|running|done|error
    total_days: int = 0
    processed_days: int = 0
    started_at: Optional[str] = None
    updated_at: Optional[str] = None
    message: Optional[str] = None


_lock = threading.Lock()
_jobs: Dict[int, _Job] = {}


def get_status(bank_id: int) -> Dict[str, Any]:
    with _lock:
        job = _jobs.get(bank_id) or _Job()
        _jobs[bank_id] = job
        out = asdict(job)
    return out


def _set_status(bank_id: int, **kwargs) -> None:
    with _lock:
        job = _jobs.get(bank_id) or _Job()
        for k, v in kwargs.items():
            setattr(job, k, v)
        job.updated_at = _iso_now()
        _jobs[bank_id] = job


def _compute_missing_days(s: Session, bank_id: int) -> list[date]:
    bank = s.execute(select(Bank).where(Bank.id == bank_id)).scalar_one_or_none()
    if bank is None:
        return []

    borrow_date = (
        s.execute(
            select(func.min(Transaction.date)).where(
                Transaction.bank_id == bank_id,
                Transaction.category == "principal",
                Transaction.amount > 0,
            )
        )
        .scalar_one()
    )
    if borrow_date is None:
        return []

    start = adjust_to_last_business_day(borrow_date)
    target = adjust_to_last_business_day(date.today())

    # For Islamic: only need the first day's rate
    if _is_islamic(bank.bank_type):
        if not _is_business_day(start):
            return []
        exists = (
            s.execute(
                select(func.count()).select_from(Rate).where(
                    Rate.bank_id == bank_id,
                    Rate.tenor_months == 1,
                    Rate.effective_date == start,
                )
            )
            .scalar_one()
            or 0
        )
        return [] if int(exists) > 0 else [start]

    # Conventional: need all business days from start..target
    existing = (
        s.execute(
            select(Rate.effective_date).where(
                Rate.bank_id == bank_id,
                Rate.tenor_months == 1,
                Rate.effective_date >= start,
                Rate.effective_date <= target,
            )
        )
        .scalars()
        .all()
    )
    have = set(existing)

    missing: list[date] = []
    d = start
    while d <= target:
        if _is_business_day(d) and d not in have:
            missing.append(d)
        d = d + timedelta(days=1)
    return missing


def ensure_started(bank_id: int) -> Dict[str, Any]:
    # If already running, just return status
    st = get_status(bank_id)
    if st.get("status") == "running":
        return st

    with SessionLocal() as s:
        missing = _compute_missing_days(s, bank_id)

    if not missing:
        _set_status(bank_id, status="done", total_days=0, processed_days=0, started_at=None, message=None)
        return get_status(bank_id)

    _set_status(
        bank_id,
        status="running",
        total_days=len(missing),
        processed_days=0,
        started_at=_iso_now(),
        message=None,
    )

    t = threading.Thread(target=_run_job, args=(bank_id,), daemon=True)
    t.start()
    return get_status(bank_id)


def is_ready(s: Session, bank_id: int) -> bool:
    st = get_status(bank_id)
    if st.get("status") == "running":
        return False
    missing = _compute_missing_days(s, bank_id)
    return len(missing) == 0


def _run_job(bank_id: int) -> None:
    try:
        with SessionLocal() as s:
            missing = _compute_missing_days(s, bank_id)
            if not missing:
                _set_status(bank_id, status="done", total_days=0, processed_days=0, message=None)
                return

            _set_status(bank_id, status="running", total_days=len(missing), processed_days=0, message=None)

            done = 0
            for day in sorted(missing):
                kib = get_kibor_offer_rates(day)

                # IMPORTANT:
                # The scraper may resolve to an earlier PDF date (e.g., holiday / missing PDF),
                # but for backfilling we must store a row for the *requested* business day,
                # otherwise that day remains "missing" forever and the job loops.
                eff = day

                rates_by_tenor = kib.by_tenor_months()

                values: list[dict] = []
                for tenor_months, offer in rates_by_tenor.items():
                    values.append(
                        {
                            "bank_id": bank_id,
                            "tenor_months": int(tenor_months),
                            "effective_date": eff,
                            "annual_rate_percent": offer,
                        }
                    )

                if values:
                    stmt = (
                        pg_insert(Rate)
                        .values(values)
                        .on_conflict_do_nothing(index_elements=["bank_id", "tenor_months", "effective_date"])
                    )
                    s.execute(stmt)
                    s.commit()

                done += 1
                _set_status(bank_id, processed_days=done)

            _set_status(bank_id, status="done", message=None)

    except Exception as e:
        _set_status(bank_id, status="error", message=str(e))
