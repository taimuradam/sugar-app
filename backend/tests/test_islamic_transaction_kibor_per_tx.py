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
        name="Loan-A",
        kibor_tenor_months=tenor_months,
        additional_rate=addl_rate_percent,
        kibor_placeholder_rate_percent=placeholder,
        max_loan_amount=None,
    )
    session.add(loan)
    session.commit()
    return bank, loan


def _add_rate(session, bank_id: int, tenor_months: int, day: date, rate_percent: Decimal):
    r = Rate(
        bank_id=bank_id,
        tenor_months=tenor_months,
        effective_date=day,
        annual_rate_percent=rate_percent,
    )
    session.add(r)
    session.commit()


def _add_tx(session, bank_id: int, loan_id: int, day: date, category: str, amount: Decimal):
    t = Transaction(
        bank_id=bank_id,
        loan_id=loan_id,
        date=day,
        category=category,
        amount=amount,
        note=None,
    )
    session.add(t)
    session.commit()
    return t


def test_islamic_kibor_rate_is_per_principal_debit_tx_date_not_single_fixed_rate(session):
    bank, loan = _mk_bank_loan(
        session,
        bank_type="islamic",
        tenor_months=1,
        addl_rate_percent=Decimal("0.0000"),
        placeholder=Decimal("0.0000"),
    )

    d1 = date(2026, 1, 1)
    d2 = date(2026, 1, 3)

    _add_rate(session, bank.id, loan.kibor_tenor_months, d1, Decimal("10.8400"))
    _add_rate(session, bank.id, loan.kibor_tenor_months, d2, Decimal("11.0000"))

    _add_tx(session, bank.id, loan.id, d1, "principal", Decimal("100.00"))
    _add_tx(session, bank.id, loan.id, d2, "principal", Decimal("200.00"))
    _add_tx(session, bank.id, loan.id, d2, "principal", Decimal("-50.00"))  # repayment: should not have kibor
    _add_tx(session, bank.id, loan.id, d2, "markup", Decimal("-1.00"))      # markup payment: should not have kibor

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
