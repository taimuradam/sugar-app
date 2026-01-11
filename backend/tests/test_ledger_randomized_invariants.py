from datetime import date, timedelta
from decimal import Decimal, getcontext
from random import Random
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

getcontext().prec = 60


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


def _to_dec(v) -> Decimal:
    return Decimal(str(v))


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


def _fifo_apply(tranches: list[Decimal], amt: Decimal) -> None:
    if amt >= 0:
        tranches.append(amt)
        return

    repay = -amt
    i = 0
    while repay > 0 and i < len(tranches):
        take = min(tranches[i], repay)
        tranches[i] -= take
        repay -= take
        if tranches[i] == 0:
            tranches.pop(i)
        else:
            i += 1


def _sum_tranches(tranches: list[Decimal]) -> Decimal:
    out = Decimal("0")
    for x in tranches:
        out += x
    return out


def test_randomized_principal_balance_invariants(session):
    rng = Random(1337)

    bank, loan = _mk_bank_loan(
        session,
        bank_type="conventional",
        tenor_months=1,
        addl_rate_percent=Decimal("0.0000"),
        placeholder=Decimal("10.0000"),
    )

    start = date(2026, 1, 1)
    end = date(2026, 3, 1)

    _add_rate(session, bank.id, loan.kibor_tenor_months, start, Decimal("12.3456"))

    day = start
    while day <= end:
        n = rng.randint(0, 3)
        for _ in range(n):
            kind = rng.random()
            if kind < 0.55:
                amt = Decimal(rng.choice([100, 250, 500, 1000, 2000]))
                _add_tx(session, bank.id, loan.id, day, "principal", amt)
            elif kind < 0.90:
                amt = Decimal(rng.choice([50, 100, 200, 300, 500, 1000]))
                _add_tx(session, bank.id, loan.id, day, "principal", -amt)
            else:
                amt = Decimal(rng.choice([25, 50, 100, 250]))
                sign = -1 if rng.random() < 0.8 else 1
                _add_tx(session, bank.id, loan.id, day, "markup", Decimal(sign) * amt)
        day += timedelta(days=1)

    rows = compute_ledger(session, bank.id, loan.id, start, end)
    assert len(rows) == (end - start).days + 1

    txs = (
        session.query(Transaction)
        .filter(Transaction.bank_id == bank.id, Transaction.loan_id == loan.id, Transaction.date <= end)
        .order_by(Transaction.date.asc(), Transaction.id.asc())
        .all()
    )

    tx_by_day: dict[date, list[Transaction]] = {}
    for t in txs:
        tx_by_day.setdefault(t.date, []).append(t)

    tranches: list[Decimal] = []
    accrued = Decimal("0")

    cur = start
    by_day = {r["date"]: r for r in rows}

    while cur <= end:
        for t in tx_by_day.get(cur, []):
            amt = _to_dec(t.amount)
            if t.category == "principal":
                _fifo_apply(tranches, amt)
            elif t.category == "markup":
                accrued += amt

        if accrued < 0:
            accrued = Decimal("0")

        expected_principal = _sum_tranches(tranches)

        got_principal = Decimal(str(by_day[cur]["principal_balance"]))
        assert got_principal >= 0
        assert expected_principal >= 0
        assert got_principal == expected_principal.quantize(Decimal("0.01"))

        got_accrued = Decimal(str(by_day[cur]["accrued_markup"]))
        assert got_accrued >= 0

        cur += timedelta(days=1)


def test_randomized_subrange_matches_fullrange_state(session):
    rng = Random(2025)

    bank, loan = _mk_bank_loan(
        session,
        bank_type="conventional",
        tenor_months=1,
        addl_rate_percent=Decimal("0.0000"),
        placeholder=Decimal("8.0000"),
    )

    start = date(2026, 1, 1)
    end = date(2026, 2, 20)

    _add_rate(session, bank.id, loan.kibor_tenor_months, start, Decimal("9.5000"))

    cur = start
    while cur <= end:
        if rng.random() < 0.35:
            _add_tx(session, bank.id, loan.id, cur, "principal", Decimal("1000.00"))
        if rng.random() < 0.25:
            _add_tx(session, bank.id, loan.id, cur, "principal", Decimal("-500.00"))
        cur += timedelta(days=1)

    full = compute_ledger(session, bank.id, loan.id, start, end)
    sub_start = date(2026, 2, 10)
    sub_end = date(2026, 2, 20)
    sub = compute_ledger(session, bank.id, loan.id, sub_start, sub_end)

    full_map = {r["date"]: r for r in full}
    sub_map = {r["date"]: r for r in sub}

    cur = sub_start
    while cur <= sub_end:
        assert Decimal(str(sub_map[cur]["principal_balance"])) == Decimal(str(full_map[cur]["principal_balance"]))
        assert Decimal(str(sub_map[cur]["accrued_markup"])) == Decimal(str(full_map[cur]["accrued_markup"]))
        cur += timedelta(days=1)