from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.bank_settings import BankSettings

def get_settings_for_year(s: Session, bank_id: int, year: int):
    row = s.execute(
        select(BankSettings).where(
            BankSettings.bank_id == bank_id,
            BankSettings.year <= year,
        ).order_by(BankSettings.year.desc())
    ).scalars().first()
    return row

def resolve_year(body_year: int | None):
    return body_year if body_year is not None else date.today().year
