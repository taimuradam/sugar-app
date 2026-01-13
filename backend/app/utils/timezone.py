from datetime import date, datetime
from zoneinfo import ZoneInfo

KARACHI_TZ = ZoneInfo("Asia/Karachi")


def now_karachi() -> datetime:
    return datetime.now(tz=KARACHI_TZ)


def today_karachi() -> date:
    return now_karachi().date()