from __future__ import annotations

import asyncio
from datetime import date

from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.bank import Bank
from app.models.rate import Rate
from app.services.kibor import get_kibor_offer_rates, adjust_to_last_business_day


def _is_islamic(bank_type: str) -> bool:
    return (bank_type or "").strip().lower() == "islamic"


def sync_kibor_rates_once(*, for_date: date | None = None) -> None:
    today = for_date or date.today()
    target = adjust_to_last_business_day(today)

    s = SessionLocal()
    try:
        banks = s.execute(select(Bank)).scalars().all()
        conventional_ids = [b.id for b in banks if not _is_islamic(b.bank_type)]
        if not conventional_ids:
            return

        rates = get_kibor_offer_rates(target)

        for bank_id in conventional_ids:
            for tenor_months, offer in rates.by_tenor_months().items():
                exists = s.execute(
                    select(Rate.id).where(
                        Rate.bank_id == bank_id,
                        Rate.tenor_months == tenor_months,
                        Rate.effective_date == rates.effective_date,
                    )
                ).scalar_one_or_none()
                if exists is not None:
                    continue

                s.add(
                    Rate(
                        bank_id=bank_id,
                        tenor_months=tenor_months,
                        effective_date=rates.effective_date,
                        annual_rate_percent=offer,
                    )
                )

        s.commit()
    finally:
        s.close()


async def kibor_sync_loop() -> None:
    if not getattr(settings, "kibor_sync_enabled", True):
        return

    interval = int(getattr(settings, "kibor_sync_interval_seconds", 3600) or 3600)
    await asyncio.sleep(3)

    while True:
        try:
            sync_kibor_rates_once()
        except Exception:
            pass

        await asyncio.sleep(max(60, interval))
