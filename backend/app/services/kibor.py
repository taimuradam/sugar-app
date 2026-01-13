from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import io
import re

import httpx
import pdfplumber


MONTH_ABBR = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]


@dataclass(frozen=True)
class KiborRates:
    effective_date: date
    offer_1m: float
    offer_3m: float
    offer_6m: float
    offer_9m: float
    offer_12m: float  # 1 year

    def by_tenor_months(self) -> dict[int, float]:
        return {
            1: self.offer_1m,
            3: self.offer_3m,
            6: self.offer_6m,
            9: self.offer_9m,
            12: self.offer_12m,
        }


def adjust_to_last_business_day(d: date) -> date:
    if d.weekday() == 5:
        return d - timedelta(days=1)
    if d.weekday() == 6:
        return d - timedelta(days=2)
    return d


def _candidate_urls(d: date) -> list[str]:
    yyyy = d.year
    mon = MONTH_ABBR[d.month - 1]
    dd = f"{d.day:02d}"
    yy = f"{d.year % 100:02d}"

    base = f"https://www.sbp.org.pk/ecodata/kibor/{yyyy}/{mon}/"
    names = [
        f"Kibor-{dd}-{mon}-{yy}.pdf",
        f"kibor-{dd}-{mon}-{yy}.pdf",
        f"KIBOR-{dd}-{mon}-{yy}.pdf",
        f"kibor-{dd}-{mon}-{yy}.PDF",
    ]
    return [base + n for n in names]


def fetch_kibor_pdf_bytes(d: date, *, timeout_s: float = 15.0) -> tuple[bytes, date]:
    probe = adjust_to_last_business_day(d)

    with httpx.Client(timeout=timeout_s, follow_redirects=True) as client:
        for _ in range(10):
            probe = adjust_to_last_business_day(probe)

            for url in _candidate_urls(probe):
                r = client.get(url)
                if r.status_code == 200 and r.content:
                    return (r.content, probe)

            probe = probe - timedelta(days=1)

    raise RuntimeError(f"kibor_pdf_not_found_for_{d.isoformat()}")


_TENOR_PATTERNS: dict[int, re.Pattern[str]] = {
    1: re.compile(r"\b1\s*[-–]?\s*month\b", re.IGNORECASE),
    3: re.compile(r"\b3\s*[-–]?\s*month\b", re.IGNORECASE),
    6: re.compile(r"\b6\s*[-–]?\s*month\b", re.IGNORECASE),
    9: re.compile(r"\b9\s*[-–]?\s*month(s)?\b", re.IGNORECASE),
    12: re.compile(r"\b(12\s*[-–]?\s*month(s)?|1\s*[-–]?\s*year)\b", re.IGNORECASE),
}

def _extract_offer_rate_for_tenor(text: str, tenor_months: int) -> float | None:
    pat = _TENOR_PATTERNS[tenor_months]
    for line in text.splitlines():
        if not pat.search(line):
            continue
        nums = re.findall(r"\d+\.\d+", line)
        if len(nums) >= 2:
            return float(nums[-1])
    return None


def parse_kibor_offer_rates(pdf_bytes: bytes) -> tuple[float, float, float, float, float]:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages)

    o1 = _extract_offer_rate_for_tenor(text, 1)
    o3 = _extract_offer_rate_for_tenor(text, 3)
    o6 = _extract_offer_rate_for_tenor(text, 6)
    o9 = _extract_offer_rate_for_tenor(text, 9)
    o12 = _extract_offer_rate_for_tenor(text, 12)

    if o1 is None or o3 is None or o6 is None or o9 is None or o12 is None:
        raise RuntimeError("kibor_parse_failed")

    return (o1, o3, o6, o9, o12)


def get_kibor_offer_rates(d: date) -> KiborRates:
    pdf_bytes, resolved_date = fetch_kibor_pdf_bytes(d)
    o1, o3, o6, o9, o12 = parse_kibor_offer_rates(pdf_bytes)
    return KiborRates(
        effective_date=resolved_date,
        offer_1m=o1,
        offer_3m=o3,
        offer_6m=o6,
        offer_9m=o9,
        offer_12m=o12,
    )
