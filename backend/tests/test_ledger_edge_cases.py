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


def test_ledger_window_includes_prior_transactions_in_state(session):
    bank, loan = _mk_bank_loan(
        session,
        bank_type="conventional",
        tenor_months=1,
        addl_rate_percent=Decimal("0.0000"),
        placeholder=Decimal("0.0000"),
    )

    _add_rate(session, bank.id, loan.kibor_tenor_months, date(2026, 1, 1), Decimal("10.0000"))
    _add_tx(session, bank.id, loan.id, date(2026, 1, 1), "principal", Decimal("1000.00"))

    rows = compute_ledger(session, bank.id, loan.id, date(2026, 1, 10), date(2026, 1, 12))
    assert len(rows) == 3

    by_day = {r["date"]: r for r in rows}
    assert by_day[date(2026, 1, 10)]["principal_balance"] == 1000.0
    assert by_day[date(2026, 1, 10)]["accrued_markup"] > 0.0


def test_fifo_repayment_consumes_oldest_tranche_first(session):
    bank, loan = _mk_bank_loan(
        session,
        bank_type="conventional",
        tenor_months=1,
        addl_rate_percent=Decimal("0.0000"),
        placeholder=Decimal("0.0000"),
    )

    _add_rate(session, bank.id, loan.kibor_tenor_months, date(2026, 1, 1), Decimal("10.0000"))
    _add_rate(session, bank.id, loan.kibor_tenor_months, date(2026, 2, 1), Decimal("12.0000"))

    _add_tx(session, bank.id, loan.id, date(2026, 1, 1), "principal", Decimal("1000.00"))
    _add_tx(session, bank.id, loan.id, date(2026, 1, 5), "principal", Decimal("500.00"))
    _add_tx(session, bank.id, loan.id, date(2026, 1, 10), "principal", Decimal("-1200.00"))

    rows = compute_ledger(session, bank.id, loan.id, date(2026, 1, 9), date(2026, 1, 12))
    by_day = {r["date"]: r for r in rows}

    assert by_day[date(2026, 1, 9)]["principal_balance"] == 1500.0
    assert by_day[date(2026, 1, 10)]["principal_balance"] == 300.0
    assert by_day[date(2026, 1, 11)]["principal_balance"] == 300.0


def test_accrued_markup_never_negative_when_markup_payment_exceeds(session):
    bank, loan = _mk_bank_loan(
        session,
        bank_type="conventional",
        tenor_months=1,
        addl_rate_percent=Decimal("0.0000"),
        placeholder=Decimal("10.0000"),
    )

    _add_tx(session, bank.id, loan.id, date(2026, 1, 1), "principal", Decimal("1000.00"))
    _add_tx(session, bank.id, loan.id, date(2026, 1, 2), "markup", Decimal("-999999.99"))

    rows = compute_ledger(session, bank.id, loan.id, date(2026, 1, 1), date(2026, 1, 3))
    by_day = {r["date"]: r for r in rows}

    assert by_day[date(2026, 1, 2)]["accrued_markup"] == 0.0
    assert by_day[date(2026, 1, 3)]["accrued_markup"] >= 0.0


def test_placeholder_rate_used_when_no_rates_exist(session):
    bank, loan = _mk_bank_loan(
        session,
        bank_type="conventional",
        tenor_months=1,
        addl_rate_percent=Decimal("1.2500"),
        placeholder=Decimal("7.1234"),
    )

    _add_tx(session, bank.id, loan.id, date(2026, 1, 1), "principal", Decimal("1000.00"))

    rows = compute_ledger(session, bank.id, loan.id, date(2026, 1, 1), date(2026, 1, 1))
    assert len(rows) == 1
    assert rows[0]["rate_percent"] == float(Decimal("7.1234") + Decimal("1.2500"))


def test_islamic_rate_locks_to_tranche_start_even_if_new_rates_appear(session):
    bank, loan = _mk_bank_loan(
        session,
        bank_type="islamic",
        tenor_months=1,
        addl_rate_percent=Decimal("0.5000"),
        placeholder=Decimal("0.0000"),
    )

    tranche_day = date(2026, 1, 20)
    later_day = date(2026, 3, 5)

    _add_rate(session, bank.id, loan.kibor_tenor_months, tranche_day, Decimal("10.0000"))
    _add_rate(session, bank.id, loan.kibor_tenor_months, date(2026, 2, 1), Decimal("99.0000"))

    _add_tx(session, bank.id, loan.id, tranche_day, "principal", Decimal("100000.00"))

    rows = compute_ledger(session, bank.id, loan.id, later_day, later_day)
    assert len(rows) == 1
    assert rows[0]["rate_percent"] == float(Decimal("10.0000") + Decimal("0.5000"))
