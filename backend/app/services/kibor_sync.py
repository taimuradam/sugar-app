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
_last_probe_borrow_min: date | None = None


def backfill_missing_kibor_rates(s: Session) -> None:
    target_day = adjust_to_last_business_day(date.today())

    banks = s.execute(select(Bank)).scalars().all()
    if not banks:
        return

    conventional_ids: list[int] = [b.id for b in banks if not _is_islamic(b.bank_type)]
    islamic_ids: list[int] = [b.id for b in banks if _is_islamic(b.bank_type)]

    borrow_dates: dict[int, date] = {}
    for bank_id in conventional_ids + islamic_ids:
        bd = (
            s.execute(
                select(func.min(Transaction.date)).where(
                    Transaction.bank_id == bank_id,
                    Transaction.category == "principal",
                    Transaction.amount > 0,
                )
            )
            .scalar_one()
        )
        if bd is not None:
            borrow_dates[bank_id] = bd

    if not borrow_dates:
        return

    start_by_bank: dict[int, date] = {}
    for bank_id, bd in borrow_dates.items():
        start_by_bank[bank_id] = adjust_to_last_business_day(bd)

    existing_by_bank: dict[int, set[date]] = {}
    for bank_id, st in start_by_bank.items():
        rows = (
            s.execute(
                select(Rate.effective_date).where(
                    Rate.bank_id == bank_id,
                    Rate.tenor_months == 1,
                    Rate.effective_date >= st,
                    Rate.effective_date <= target_day,
                )
            )
            .scalars()
            .all()
        )
        existing_by_bank[bank_id] = set(rows)

    day_to_banks: dict[date, set[int]] = {}
    for bank_id, st in start_by_bank.items():
        if bank_id in islamic_ids:
            if _is_business_day(st) and st not in existing_by_bank.get(bank_id, set()):
                day_to_banks.setdefault(st, set()).add(bank_id)
            continue

        day = st
        existing = existing_by_bank.get(bank_id, set())
        while day <= target_day:
            if _is_business_day(day) and day not in existing:
                day_to_banks.setdefault(day, set()).add(bank_id)
            day = day + timedelta(days=1)

    if not day_to_banks:
        return

    for day in sorted(day_to_banks.keys()):
        bank_ids = sorted(day_to_banks[day])
        if not bank_ids:
            continue

        kib = get_kibor_offer_rates(day)
        eff = kib.effective_date
        rates_by_tenor = kib.by_tenor_months()

        values: list[dict] = []
        for bank_id in bank_ids:
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


def maybe_refresh_kibor_rates(s: Session) -> None:
    global _last_probe_day, _last_probe_ts, _last_probe_latest, _last_probe_borrow_min

    target_day = adjust_to_last_business_day(date.today())
    latest = s.execute(select(func.max(Rate.effective_date))).scalar_one()

    borrow_min = (
        s.execute(
            select(func.min(Transaction.date)).where(
                Transaction.category == "principal",
                Transaction.amount > 0,
            )
        )
        .scalar_one()
    )

    now = datetime.utcnow()
    if (
        _last_probe_day == target_day
        and _last_probe_latest == latest
        and _last_probe_borrow_min == borrow_min
        and _last_probe_ts is not None
        and (now - _last_probe_ts) < timedelta(minutes=15)
    ):
        return

    _last_probe_day = target_day
    _last_probe_latest = latest
    _last_probe_borrow_min = borrow_min
    _last_probe_ts = now

    backfill_missing_kibor_rates(s)


def sync_kibor_rates_once() -> None:
    with SessionLocal() as s:
        backfill_missing_kibor_rates(s)


async def kibor_sync_loop() -> None:
    if not getattr(settings, "kibor_sync_enabled", True):
        return

    interval = int(getattr(settings, "kibor_sync_interval_seconds", 3600) or 3600)
    await asyncio.sleep(3)

    while True:
        try:
            sync_kibor_rates_once()
        except Exception as e:
            logging.exception("kibor_sync failed", exc_info=e)

        await asyncio.sleep(max(60, interval))