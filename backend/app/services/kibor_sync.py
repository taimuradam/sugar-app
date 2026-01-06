from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta
from app.models.transaction import Transaction

from sqlalchemy import select, func
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.bank import Bank
from app.models.rate import Rate
from app.services.kibor import get_kibor_offer_rates, adjust_to_last_business_day


def _is_islamic(bank_type: str) -> bool:
    return (bank_type or "").strip().lower() == "islamic"


def _is_business_day(d: date) -> bool:
    return d.weekday() < 5


_last_probe_day: date | None = None
_last_probe_ts: datetime | None = None
_last_probe_latest: date | None = None


def backfill_missing_kibor_rates(s: Session) -> None:
    target_day = adjust_to_last_business_day(date.today())

    banks = s.execute(select(Bank)).scalars().all()
    conventional_banks = [b for b in banks if not _is_islamic(b.bank_type)]
    if not conventional_banks:
        return

    borrow_dates: dict[int, date] = {}
    for b in conventional_banks:
        bd = (
            s.execute(
                select(func.min(Transaction.date)).where(
                    Transaction.bank_id == b.id,
                    Transaction.category == "principal",
                    Transaction.amount > 0,
                )
            )
            .scalar_one()
        )
        if bd is not None:
            borrow_dates[b.id] = bd

    if not borrow_dates:
        return

    start_by_bank: dict[int, date] = {}
    for bank_id, bd in borrow_dates.items():
        latest_for_bank: date | None = (
            s.execute(select(func.max(Rate.effective_date)).where(Rate.bank_id == bank_id)).scalar_one()
        )
        if latest_for_bank is None:
            start_by_bank[bank_id] = bd
        else:
            start_by_bank[bank_id] = max(bd, latest_for_bank + timedelta(days=1))

    global_start = min(start_by_bank.values())

    day = global_start
    while day <= target_day:
        if not _is_business_day(day):
            day = day + timedelta(days=1)
            continue

        active_bank_ids = [bid for bid, st in start_by_bank.items() if day >= st]
        if not active_bank_ids:
            day = day + timedelta(days=1)
            continue

        kib = get_kibor_offer_rates(day)
        eff = kib.effective_date
        rates_by_tenor = kib.by_tenor_months()

        values = []
        for bank_id in active_bank_ids:
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

        day = day + timedelta(days=1)


def maybe_refresh_kibor_rates(s: Session) -> None:
    target_day = adjust_to_last_business_day(date.today())
    latest: date | None = s.execute(select(func.max(Rate.effective_date))).scalar_one()

    if latest is not None and latest >= target_day:
        return

    global _last_probe_day, _last_probe_ts, _last_probe_latest

    now = datetime.utcnow()
    if (
        _last_probe_day == target_day
        and _last_probe_latest == latest
        and _last_probe_ts is not None
        and (now - _last_probe_ts) < timedelta(minutes=15)
    ):
        return

    _last_probe_day = target_day
    _last_probe_latest = latest
    _last_probe_ts = now

    backfill_missing_kibor_rates(s)


def sync_kibor_rates_once() -> None:
    with SessionLocal() as s:
        maybe_refresh_kibor_rates(s)


async def kibor_sync_loop() -> None:
    if not getattr(settings, "kibor_sync_enabled", True):
        return

    interval = int(getattr(settings, "kibor_sync_interval_seconds", 3600) or 3600)

    await asyncio.sleep(1)

    try:
        sync_kibor_rates_once()
    except Exception:
        logging.exception("kibor_sync_startup_backfill_failed")

    while True:
        try:
            sync_kibor_rates_once()
        except Exception:
            logging.exception("kibor_sync_failed")

        await asyncio.sleep(max(60, interval))