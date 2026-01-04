from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import select
import xlsxwriter
from app.models.bank import Bank
from app.services.ledger import compute_ledger

def build_bank_report(s: Session, bank_id: int, start: date, end: date, out_file):
    bank = s.execute(select(Bank).where(Bank.id == bank_id)).scalar_one()
    rows = compute_ledger(s, bank_id, start, end)
    wb = xlsxwriter.Workbook(out_file, {"in_memory": True})
    ws = wb.add_worksheet("Running Finance")
    ws.write_row(0, 0, ["Bank", bank.name])
    ws.write_row(2, 0, ["Date", "Principal Balance", "Daily Markup", "Accrued Markup", "Rate %"])
    r = 3
    for row in rows:
        ws.write(r, 0, str(row["date"]))
        ws.write_number(r, 1, row["principal_balance"])
        ws.write_number(r, 2, row["daily_markup"])
        ws.write_number(r, 3, row["accrued_markup"])
        ws.write_number(r, 4, row["rate_percent"])
        r += 1
    wb.close()
