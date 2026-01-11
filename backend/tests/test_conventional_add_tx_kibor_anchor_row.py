from datetime import date
from decimal import Decimal, getcontext
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, insert
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.bank import Bank
from app.models.loan import Loan
from app.models.rate import Rate
from app.api.routes.transactions import add_tx
from app.schemas.transaction import TxCreate
import app.api.routes.transactions as tx_routes

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


class _FakeKibor:
    def __init__(self, mapping: dict[int, float]):
        self._m = mapping

    def by_tenor_months(self) -> dict[int, float]:
        return dict(self._m)


class _SQLiteInsertIgnore:
    def __init__(self, table):
        self._stmt = insert(table)

    def values(self, vals: dict):
        self._stmt = self._stmt.values(**vals).prefix_with("OR IGNORE")
        return self

    def on_conflict_do_nothing(self, index_elements=None):
        return self

    def __clause_element__(self):
        return self._stmt


def test_add_tx_conventional_inserts_rate_row_on_principal_debit(session, monkeypatch):
    bank, loan = _mk_bank_loan(
        session,
        bank_type="conventional",
        tenor_months=1,
        additional_rate=Decimal("0"),
        placeholder=Decimal("0"),
    )

    monkeypatch.setattr(tx_routes, "get_kibor_offer_rates", lambda d: _FakeKibor({1: 10.84}))
    monkeypatch.setattr(tx_routes, "pg_insert", lambda table: _SQLiteInsertIgnore(table))

    called = {"n": 0}

    def _fake_ensure_started(bank_id: int, loan_id: int):
        called["n"] += 1
        return {"status": "running"}

    monkeypatch.setattr(tx_routes, "ensure_started", _fake_ensure_started)

    out = add_tx(
        bank.id,
        loan.id,
        TxCreate(date=date(2025, 12, 11), category="principal", amount=100.0, note="borrow"),
        s=session,
        u={"sub": "tester"},
    )

    assert out.kibor_rate_percent == pytest.approx(10.84, rel=0, abs=1e-9)

    r = session.execute(
        select(Rate).where(
            Rate.bank_id == bank.id,
            Rate.tenor_months == 1,
            Rate.effective_date == date(2025, 12, 11),
        )
    ).scalar_one()
    assert float(r.annual_rate_percent) == pytest.approx(10.84, rel=0, abs=1e-9)

    loan2 = session.execute(select(Loan).where(Loan.id == loan.id)).scalar_one()
    assert float(loan2.kibor_placeholder_rate_percent) == pytest.approx(10.84, rel=0, abs=1e-9)

    assert called["n"] == 1
