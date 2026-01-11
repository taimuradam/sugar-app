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

    connection = engine.connect()
    trans = connection.begin()
    SessionLocal = sessionmaker(bind=connection, autoflush=False, autocommit=False, future=True)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()
        trans.rollback()
        connection.close()


def _mk_bank_loan(session, bank_type: str, tenor_months: int, addl_rate_percent: Decimal, placeholder: Decimal):
    bank = Bank(
        name=f"TestBank-{uuid4().hex[:10]}",
        bank_type=bank_type,
        additional_rate=None,
    )
    session.add(bank)
    session.flush()

    loan = Loan(
        bank_id=bank.id,
        name=f"Loan-{uuid4().hex[:10]}",
        kibor_tenor_months=int(tenor_months),
        additional_rate=float(addl_rate_percent),
        kibor_placeholder_rate_percent=float(placeholder),
        max_loan_amount=None,
    )
    session.add(loan)
    session.flush()
    session.commit()
    return bank, loan


def _add_rate(session, bank_id: int, tenor_months: int, effective: date, annual_rate_percent: Decimal):
    r = Rate(
        bank_id=bank_id,
        tenor_months=int(tenor_months),
        effective_date=effective,
        annual_rate_percent=float(annual_rate_percent),
    )
    session.add(r)
    session.commit()
    return r


def _add_tx(session, bank_id: int, loan_id: int, d: date, category: str, amount: Decimal):
    t = Transaction(
        bank_id=bank_id,
        loan_id=loan_id,
        date=d,
        category=category,
        amount=float(amount),
        note=None,
    )
    session.add(t)
    session.commit()
    return t


def test_islamic_ledger_shows_rate_steps_for_three_principal_debits(session):
    bank, loan = _mk_bank_loan(
        session,
        bank_type="islamic",
        tenor_months=1,
        addl_rate_percent=Decimal("0.0000"),
        placeholder=Decimal("0.0000"),
    )

    d1 = date(2026, 1, 1)
    d2 = date(2026, 1, 2)
    d3 = date(2026, 1, 3)

    _add_rate(session, bank.id, loan.kibor_tenor_months, d1, Decimal("10.0000"))
    _add_rate(session, bank.id, loan.kibor_tenor_months, d2, Decimal("12.0000"))
    _add_rate(session, bank.id, loan.kibor_tenor_months, d3, Decimal("14.0000"))

    _add_tx(session, bank.id, loan.id, d1, "principal", Decimal("100.00"))
    _add_tx(session, bank.id, loan.id, d2, "principal", Decimal("100.00"))
    _add_tx(session, bank.id, loan.id, d3, "principal", Decimal("100.00"))

    rows = compute_ledger(session, bank.id, loan.id, d1, d3)
    by_day = {r["date"]: r for r in rows}

    assert by_day[d1]["rate_percent"] == pytest.approx(10.0, rel=0, abs=1e-9)
    assert by_day[d2]["rate_percent"] == pytest.approx(11.0, rel=0, abs=1e-9)  # avg(10,12)
    assert by_day[d3]["rate_percent"] == pytest.approx(12.0, rel=0, abs=1e-9)  # avg(10,12,14)