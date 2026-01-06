from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bank_settings import BankSettings


def get_settings_for_year(s: Session, bank_id: int, year: int):
    row = (
        s.execute(
            select(BankSettings)
            .where(BankSettings.bank_id == bank_id, BankSettings.year <= year)
            .order_by(BankSettings.year.desc())
        )
        .scalars()
        .first()
    )
    if row is not None:
        return row

    return (
        s.execute(select(BankSettings).where(BankSettings.bank_id == bank_id).order_by(BankSettings.year.asc()))
        .scalars()
        .first()
    )


def resolve_year(body_year: int | None):
    return body_year if body_year is not None else date.today().year