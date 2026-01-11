from datetime import date
from decimal import Decimal, getcontext
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.bank import Bank
from app.models.loan import Loan
from app.models.rate import Rate
from app.models.transaction import Transaction
from app.services.ledger import compute_ledger

getcontext().prec = 50


@pytest.fixture()
def session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    connection = engine.connect()
    trans = connection.begin()
    s = SessionLocal(bind=connection)
    try:
        yield s
    finally:
        s.close()
        trans.rollback()
        connection.close()


def test_conventional_tranche_rates_lock_within_month_and_sum_markup(session):
    bank = Bank(name=f"conv-{uuid4()}", bank_type="conventional")
    session.add(bank)
    session.flush()

    loan = Loan(
        bank_id=bank.id,
        name="L1",
        kibor_tenor_months=1,
        kibor_placeholder_rate_percent=Decimal("0"),
        additional_rate=None,
    )
    session.add(loan)
    session.flush()

    session.add_all(
        [
            Rate(bank_id=bank.id, tenor_months=1, effective_date=date(2025, 12, 8), annual_rate_percent=Decimal("11.29")),
            Rate(bank_id=bank.id, tenor_months=1, effective_date=date(2025, 12, 21), annual_rate_percent=Decimal("11.06")),
            Rate(bank_id=bank.id, tenor_months=1, effective_date=date(2026, 1, 1), annual_rate_percent=Decimal("12.00")),
        ]
    )

    session.add_all(
        [
            Transaction(bank_id=bank.id, loan_id=loan.id, date=date(2025, 12, 8), category="principal", amount=Decimal("1000"), note="borrow1"),
            Transaction(bank_id=bank.id, loan_id=loan.id, date=date(2025, 12, 21), category="principal", amount=Decimal("1000"), note="borrow2"),
        ]
    )
    session.commit()

    rows = compute_ledger(session, bank.id, loan.id, date(2025, 12, 8), date(2026, 1, 2))
    by_day = {r["date"]: r for r in rows}

    d1 = Decimal("36500")

    m_1129 = (Decimal("1000") * Decimal("11.29")) / d1
    m_1106 = (Decimal("1000") * Decimal("11.06")) / d1
    m_jan = (Decimal("2000") * Decimal("12.00")) / d1

    assert by_day[date(2025, 12, 20)]["daily_markup"] == pytest.approx(float(m_1129), rel=0, abs=1e-12)

    expected_1221 = m_1129 + m_1106
    assert by_day[date(2025, 12, 21)]["daily_markup"] == pytest.approx(float(expected_1221), rel=0, abs=1e-12)

    assert by_day[date(2025, 12, 31)]["daily_markup"] == pytest.approx(float(expected_1221), rel=0, abs=1e-12)

    expected_weighted = (Decimal("11.29") + Decimal("11.06")) / Decimal("2")
    assert by_day[date(2025, 12, 21)]["rate_percent"] == pytest.approx(float(expected_weighted), rel=0, abs=1e-12)

    assert by_day[date(2026, 1, 1)]["daily_markup"] == pytest.approx(float(m_jan), rel=0, abs=1e-12)
    assert by_day[date(2026, 1, 1)]["rate_percent"] == pytest.approx(12.00, rel=0, abs=1e-12)
