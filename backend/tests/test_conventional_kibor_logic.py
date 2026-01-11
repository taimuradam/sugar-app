from datetime import date
from decimal import Decimal, getcontext
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.bank import Bank
from app.models.loan import Loan
from app.models.rate import Rate
from app.models.transaction import Transaction
from app.services.ledger import compute_ledger
from app.api.routes.transactions import _attach_kibor_rates

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


def _mk_bank_loan(session, bank_type: str, tenor_months: int, additional_rate: Decimal, placeholder: Decimal):
    bank = Bank(
        name=f"TestBank-{uuid4().hex[:10]}",
        bank_type=bank_type,
        additional_rate=None,
    )
    session.add(bank)
    session.flush()

    loan = Loan(
        bank_id=bank.id,
        name=f"Loan-{uuid4().hex[:8]}",
        kibor_tenor_months=tenor_months,
        additional_rate=float(additional_rate),
        kibor_placeholder_rate_percent=float(placeholder),
        max_loan_amount=Decimal("1000000000"),
    )
    session.add(loan)
    session.commit()
    session.refresh(bank)
    session.refresh(loan)
    return bank, loan


def test_conventional_attach_kibor_rates_per_tx_anchor_date(session):
    bank, loan = _mk_bank_loan(
        session,
        bank_type="conventional",
        tenor_months=1,
        additional_rate=Decimal("0"),
        placeholder=Decimal("0"),
    )

    session.add_all(
        [
            Rate(bank_id=bank.id, tenor_months=1, effective_date=date(2025, 12, 11), annual_rate_percent=Decimal("10.84")),
            Rate(bank_id=bank.id, tenor_months=1, effective_date=date(2025, 12, 22), annual_rate_percent=Decimal("11.00")),
            Rate(bank_id=bank.id, tenor_months=1, effective_date=date(2026, 1, 1), annual_rate_percent=Decimal("12.00")),
        ]
    )

    session.add_all(
        [
            Transaction(bank_id=bank.id, loan_id=loan.id, date=date(2025, 12, 11), category="principal", amount=Decimal("100"), note="borrow1"),
            Transaction(bank_id=bank.id, loan_id=loan.id, date=date(2025, 12, 22), category="principal", amount=Decimal("50"), note="borrow2"),
            Transaction(bank_id=bank.id, loan_id=loan.id, date=date(2025, 12, 23), category="markup", amount=Decimal("0"), note="noop"),
            Transaction(bank_id=bank.id, loan_id=loan.id, date=date(2025, 12, 24), category="principal", amount=Decimal("-10"), note="repay"),
        ]
    )
    session.commit()

    txs = (
        session.execute(
            select(Transaction)
            .where(Transaction.bank_id == bank.id, Transaction.loan_id == loan.id)
            .order_by(Transaction.date.asc(), Transaction.id.asc())
        )
        .scalars()
        .all()
    )

    out = _attach_kibor_rates(session, bank, loan, txs)

    assert out[0].kibor_rate_percent == pytest.approx(10.84, rel=0, abs=1e-9)
    assert out[1].kibor_rate_percent == pytest.approx(11.00, rel=0, abs=1e-9)
    assert out[2].kibor_rate_percent is None
    assert out[3].kibor_rate_percent is None


def test_conventional_ledger_rate_updates_on_month_start(session):
    bank, loan = _mk_bank_loan(
        session,
        bank_type="conventional",
        tenor_months=1,
        additional_rate=Decimal("0"),
        placeholder=Decimal("0"),
    )

    session.add_all(
        [
            Rate(bank_id=bank.id, tenor_months=1, effective_date=date(2025, 12, 11), annual_rate_percent=Decimal("10.84")),
            Rate(bank_id=bank.id, tenor_months=1, effective_date=date(2025, 12, 22), annual_rate_percent=Decimal("11.00")),
            Rate(bank_id=bank.id, tenor_months=1, effective_date=date(2026, 1, 1), annual_rate_percent=Decimal("12.00")),
        ]
    )

    session.add_all(
        [
            Transaction(bank_id=bank.id, loan_id=loan.id, date=date(2025, 12, 11), category="principal", amount=Decimal("100"), note="borrow1"),
            Transaction(bank_id=bank.id, loan_id=loan.id, date=date(2025, 12, 22), category="principal", amount=Decimal("50"), note="borrow2"),
        ]
    )
    session.commit()

    rows = compute_ledger(session, bank.id, loan.id, date(2025, 12, 11), date(2026, 1, 5))
    by_day = {r["date"]: r for r in rows}

    assert by_day[date(2025, 12, 11)]["rate_percent"] == pytest.approx(10.84, rel=0, abs=1e-9)
    assert by_day[date(2025, 12, 21)]["rate_percent"] == pytest.approx(10.84, rel=0, abs=1e-9)

    expected_weighted = (100 * 10.84 + 50 * 11.00) / 150
    assert by_day[date(2025, 12, 22)]["rate_percent"] == pytest.approx(expected_weighted, rel=0, abs=1e-9)
    assert by_day[date(2025, 12, 31)]["rate_percent"] == pytest.approx(expected_weighted, rel=0, abs=1e-9)

    assert by_day[date(2026, 1, 1)]["rate_percent"] == pytest.approx(12.00, rel=0, abs=1e-9)
    assert by_day[date(2026, 1, 5)]["rate_percent"] == pytest.approx(12.00, rel=0, abs=1e-9)
