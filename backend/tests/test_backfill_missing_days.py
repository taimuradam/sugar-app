from datetime import date as _date
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
import app.services.kibor_backfill as kb

getcontext().prec = 50


@pytest.fixture(scope="session")
def engine():
    eng = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture()
def session(engine):
    connection = engine.connect()
    trans = connection.begin()
    Session = sessionmaker(bind=connection, autoflush=False, autocommit=False, future=True)
    s = Session()
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


def _add_rate(session, bank_id: int, tenor_months: int, effective: _date, annual_rate_percent: Decimal):
    r = Rate(
        bank_id=bank_id,
        tenor_months=int(tenor_months),
        effective_date=effective,
        annual_rate_percent=float(annual_rate_percent),
    )
    session.add(r)
    session.commit()
    return r


def _add_tx(session, bank_id: int, loan_id: int, d: _date, category: str, amount: Decimal):
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


def _freeze_today(monkeypatch, fixed: _date):
    class FrozenDate(_date):
        @classmethod
        def today(cls):
            return fixed

    monkeypatch.setattr(kb, "date", FrozenDate)


def test_missing_days_conventional_includes_month_starts_and_principal_dates(session, monkeypatch):
    bank, loan = _mk_bank_loan(
        session,
        bank_type="conventional",
        tenor_months=1,
        addl_rate_percent=Decimal("0"),
        placeholder=Decimal("0"),
    )

    _freeze_today(monkeypatch, _date(2026, 3, 15))

    d1 = _date(2026, 1, 20)
    d2 = _date(2026, 2, 10)

    _add_tx(session, bank.id, loan.id, d1, "principal", Decimal("1000.00"))
    _add_tx(session, bank.id, loan.id, d2, "principal", Decimal("500.00"))

    _add_rate(session, bank.id, loan.kibor_tenor_months, _date(2026, 1, 1), Decimal("10.0"))
    _add_rate(session, bank.id, loan.kibor_tenor_months, _date(2026, 2, 1), Decimal("11.0"))

    missing = kb._compute_missing_days(session, bank.id, loan.id)

    expected_anchors = {
        _date(2026, 1, 20),
        _date(2026, 2, 10),
        _date(2026, 1, 1),
        _date(2026, 2, 1),
        _date(2026, 3, 1),
    }

    assert set(missing).issubset(expected_anchors)
    assert _date(2026, 1, 1) not in missing
    assert _date(2026, 2, 1) not in missing
    assert _date(2026, 1, 20) in missing
    assert _date(2026, 2, 10) in missing
    assert _date(2026, 3, 1) in missing


def test_missing_days_islamic_only_principal_dates(session, monkeypatch):
    bank, loan = _mk_bank_loan(
        session,
        bank_type="islamic",
        tenor_months=1,
        addl_rate_percent=Decimal("0"),
        placeholder=Decimal("0"),
    )

    _freeze_today(monkeypatch, _date(2026, 3, 15))

    d1 = _date(2026, 1, 20)
    d2 = _date(2026, 2, 10)

    _add_tx(session, bank.id, loan.id, d1, "principal", Decimal("1000.00"))
    _add_tx(session, bank.id, loan.id, d2, "principal", Decimal("500.00"))

    _add_rate(session, bank.id, loan.kibor_tenor_months, d1, Decimal("10.0"))

    missing = kb._compute_missing_days(session, bank.id, loan.id)

    assert set(missing) == {d2}
