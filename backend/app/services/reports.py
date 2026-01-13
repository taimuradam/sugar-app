from __future__ import annotations

from datetime import date, datetime, time
from collections import defaultdict

import xlsxwriter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bank import Bank
from app.models.loan import Loan
from app.models.transaction import Transaction
from app.services.ledger import compute_ledger


def _month_key(d: date) -> tuple[int, int]:
    return (d.year, d.month)


def build_loan_report(s: Session, bank_id: int, loan_id: int, start: date, end: date, out_file):
    # Core entities
    bank = s.execute(select(Bank).where(Bank.id == bank_id)).scalar_one()
    loan = s.execute(select(Loan).where(Loan.id == loan_id, Loan.bank_id == bank_id)).scalar_one()

    # Ledger rows (daily)
    rows = compute_ledger(s, bank_id, loan_id, start, end)

    # Transaction detail (within range)
    txs = (
        s.execute(
            select(Transaction)
            .where(
                Transaction.bank_id == bank_id,
                Transaction.loan_id == loan_id,
                Transaction.date >= start,
                Transaction.date <= end,
            )
            .order_by(Transaction.date.asc(), Transaction.id.asc())
        )
        .scalars()
        .all()
    )

    wb = xlsxwriter.Workbook(out_file, {"in_memory": True})
    base_font = "Calibri"

    # ----------------------------
    # Formats (simple + readable)
    # ----------------------------
    meta_label = wb.add_format({"bold": True, "font_name": base_font, "font_size": 11, "font_color": "#334155"})
    meta_value = wb.add_format({"font_name": base_font, "font_size": 11, "font_color": "#0f172a"})
    subtle = wb.add_format({"font_name": base_font, "font_size": 10, "font_color": "#64748b"})

    header = wb.add_format(
        {
            "bold": True,
            "font_name": base_font,
            "font_size": 11,
            "bg_color": "#F1F5F9",
            "border": 1,
            "align": "center",
            "valign": "vcenter",
        }
    )

    date_fmt = wb.add_format({"font_name": base_font, "font_size": 11, "num_format": "yyyy-mm-dd", "border": 1})
    money2 = wb.add_format(
        {"font_name": base_font, "font_size": 11, "num_format": "#,##0.00", "border": 1, "align": "right"}
    )
    money6 = wb.add_format(
        {"font_name": base_font, "font_size": 11, "num_format": "#,##0.000000", "border": 1, "align": "right"}
    )
    rate4 = wb.add_format(
        {"font_name": base_font, "font_size": 11, "num_format": "0.0000", "border": 1, "align": "right"}
    )
    int0 = wb.add_format(
        {"font_name": base_font, "font_size": 11, "num_format": "0", "border": 1, "align": "right"}
    )
    text_cell = wb.add_format({"font_name": base_font, "font_size": 11, "border": 1, "align": "left"})

    total_label = wb.add_format(
        {
            "bold": True,
            "font_name": base_font,
            "font_size": 11,
            "bg_color": "#F8FAFC",
            "border": 1,
            "align": "left",
        }
    )
    total_money2 = wb.add_format(
        {
            "bold": True,
            "font_name": base_font,
            "font_size": 11,
            "bg_color": "#F8FAFC",
            "border": 1,
            "num_format": "#,##0.00",
            "align": "right",
        }
    )
    total_money6 = wb.add_format(
        {
            "bold": True,
            "font_name": base_font,
            "font_size": 11,
            "bg_color": "#F8FAFC",
            "border": 1,
            "num_format": "#,##0.000000",
            "align": "right",
        }
    )
    total_rate4 = wb.add_format(
        {
            "bold": True,
            "font_name": base_font,
            "font_size": 11,
            "bg_color": "#F8FAFC",
            "border": 1,
            "num_format": "0.0000",
            "align": "right",
        }
    )

    # Zebra stripe formats (keep same number formats + borders)
    stripe_date = wb.add_format({"bg_color": "#FBFDFF", "num_format": "yyyy-mm-dd"})
    stripe_money2 = wb.add_format({"bg_color": "#FBFDFF", "num_format": "#,##0.00", "align": "right"})
    stripe_money6 = wb.add_format({"bg_color": "#FBFDFF", "num_format": "#,##0.000000", "align": "right"})
    stripe_rate4 = wb.add_format({"bg_color": "#FBFDFF", "num_format": "0.0000", "align": "right"})
    stripe_int0 = wb.add_format({"bg_color": "#FBFDFF", "num_format": "0", "align": "right"})
    stripe_text = wb.add_format({"bg_color": "#FBFDFF", "align": "left"})
    for f in (stripe_date, stripe_money2, stripe_money6, stripe_rate4, stripe_int0, stripe_text):
        f.set_border(1)
        f.set_font_name(base_font)
        f.set_font_size(11)

    # ----------------------------
    # Sheet 1: Running Finance (tests expect this)
    # ----------------------------
    ws = wb.add_worksheet("Running Finance")

    ws.set_column(0, 0, 12)  # Date
    ws.set_column(1, 1, 20)  # Principal Balance
    ws.set_column(2, 3, 18)  # Markup columns
    ws.set_column(4, 4, 10)  # Rate %

    ws.write(0, 0, "Bank", meta_label)
    ws.write(0, 1, bank.name, meta_value)

    ws.write(1, 0, "Loan", meta_label)
    ws.write(1, 1, loan.name, meta_value)

    ws.write(2, 0, "Range", meta_label)
    ws.write(2, 1, f"{start} to {end}", subtle)

    ws.write(2, 3, "Generated", meta_label)
    ws.write(2, 4, datetime.now().strftime("%Y-%m-%d %H:%M"), subtle)

    headers = ["Date", "Principal Balance", "Daily Markup", "Accrued Markup", "Rate %"]
    ws.set_row(3, 18)
    for c, h in enumerate(headers):
        ws.write(3, c, h, header)

    # Keep header visible and avoid horizontal drift
    ws.freeze_panes(4, 1)

    r = 4
    for row in rows:
        dt = datetime.combine(row["date"], time.min)
        ws.write_datetime(r, 0, dt, date_fmt)
        ws.write_number(r, 1, row["principal_balance"], money2)
        # Display more precision; value remains exact in the file
        ws.write_number(r, 2, row["daily_markup"], money6)
        ws.write_number(r, 3, row["accrued_markup"], money6)
        ws.write_number(r, 4, row["rate_percent"], rate4)
        r += 1

    last_data_row = r - 1

    if last_data_row >= 4:
        ws.autofilter(3, 0, last_data_row, 4)

        # Zebra striping (subtle)
        ws.conditional_format(
            4, 0, last_data_row, 0, {"type": "formula", "criteria": "=MOD(ROW(),2)=0", "format": stripe_date}
        )
        ws.conditional_format(
            4, 1, last_data_row, 1, {"type": "formula", "criteria": "=MOD(ROW(),2)=0", "format": stripe_money2}
        )
        ws.conditional_format(
            4, 2, last_data_row, 3, {"type": "formula", "criteria": "=MOD(ROW(),2)=0", "format": stripe_money6}
        )
        ws.conditional_format(
            4, 4, last_data_row, 4, {"type": "formula", "criteria": "=MOD(ROW(),2)=0", "format": stripe_rate4}
        )

        # Totals row
        total_row = last_data_row + 1
        last_excel = last_data_row + 1  # Excel row number (1-based) for last data row

        ws.write(total_row, 0, "Totals", total_label)
        ws.write_formula(total_row, 1, f"=B{last_excel}", total_money2)
        ws.write_formula(total_row, 2, f"=SUM(C5:C{last_excel})", total_money6)
        ws.write_formula(total_row, 3, f"=D{last_excel}", total_money6)
        ws.write_formula(total_row, 4, f"=E{last_excel}", total_rate4)

        ws.set_landscape()
        ws.fit_to_pages(1, 0)

    # ----------------------------
    # Sheet 2: Summary (exec-friendly)
    # ----------------------------
    summary = wb.add_worksheet("Summary")
    summary.set_column(0, 0, 22)
    summary.set_column(1, 1, 44)

    title = wb.add_format({"bold": True, "font_name": base_font, "font_size": 14, "font_color": "#0f172a"})
    summary.write(0, 0, "Loan Summary", title)

    summary.write(2, 0, "Bank", meta_label)
    summary.write(2, 1, bank.name, meta_value)

    summary.write(3, 0, "Loan", meta_label)
    summary.write(3, 1, loan.name, meta_value)

    summary.write(4, 0, "Range", meta_label)
    summary.write(4, 1, f"{start} to {end}", subtle)

    if last_data_row >= 4:
        totals_excel_row = (last_data_row + 1) + 1  # totals row (0-based) -> Excel row number
        summary.write(6, 0, "Ending Principal", meta_label)
        summary.write_formula(6, 1, f"='Running Finance'!B{totals_excel_row}", money2)

        summary.write(7, 0, "Total Daily Markup (sum)", meta_label)
        summary.write_formula(7, 1, f"='Running Finance'!C{totals_excel_row}", money6)

        summary.write(8, 0, "Ending Accrued Markup", meta_label)
        summary.write_formula(8, 1, f"='Running Finance'!D{totals_excel_row}", money6)

        summary.write(9, 0, "Ending Rate %", meta_label)
        summary.write_formula(9, 1, f"='Running Finance'!E{totals_excel_row}", rate4)
    else:
        summary.write(6, 0, "Note", meta_label)
        summary.write(6, 1, "No ledger rows exist for the selected date range.", subtle)

    # ----------------------------
    # Sheet 3: Transactions (transaction-level detail)
    # ----------------------------
    tx_ws = wb.add_worksheet("Transactions")

    tx_ws.set_column(0, 0, 12)  # Date
    tx_ws.set_column(1, 1, 12)  # Category
    tx_ws.set_column(2, 3, 18)  # Principal / Markup deltas
    tx_ws.set_column(4, 4, 18)  # Amount (raw)
    tx_ws.set_column(5, 5, 28)  # Note
    tx_ws.set_column(6, 7, 18)  # EOD lookups

    tx_ws.write(0, 0, "Bank", meta_label)
    tx_ws.write(0, 1, bank.name, meta_value)
    tx_ws.write(1, 0, "Loan", meta_label)
    tx_ws.write(1, 1, loan.name, meta_value)
    tx_ws.write(2, 0, "Range", meta_label)
    tx_ws.write(2, 1, f"{start} to {end}", subtle)

    tx_headers = [
        "Date",
        "Category",
        "Principal Δ",
        "Markup Δ",
        "Amount",
        "Note",
        "Principal Balance",
        "Accrued Markup",
    ]
    tx_ws.set_row(3, 18)
    for c, h in enumerate(tx_headers):
        tx_ws.write(3, c, h, header)

    tx_ws.freeze_panes(4, 1)

    tr = 4
    for t in txs:
        dt = datetime.combine(t.date, time.min)
        tx_ws.write_datetime(tr, 0, dt, date_fmt)
        tx_ws.write(tr, 1, (t.category or "").lower(), text_cell)

        amt = float(t.amount)

        # Split into principal / markup delta columns for quick scanning
        if (t.category or "").lower() == "principal":
            tx_ws.write_number(tr, 2, amt, money2)
            tx_ws.write_number(tr, 3, 0.0, money2)
        elif (t.category or "").lower() == "markup":
            tx_ws.write_number(tr, 2, 0.0, money2)
            tx_ws.write_number(tr, 3, amt, money2)
        else:
            tx_ws.write_number(tr, 2, 0.0, money2)
            tx_ws.write_number(tr, 3, 0.0, money2)

        tx_ws.write_number(tr, 4, amt, money2)
        tx_ws.write(tr, 5, t.note or "", text_cell)

        # Lookup EOD balances from Running Finance by date
        # (Uses a big range so it works regardless of ledger length)
        excel_row = tr + 1  # 1-based row index for formula
        tx_ws.write_formula(
            tr,
            6,
            f'=IFERROR(VLOOKUP(A{excel_row},\'Running Finance\'!$A$5:$E$100000,2,FALSE),"")',
            money2,
        )
        tx_ws.write_formula(
            tr,
            7,
            f'=IFERROR(VLOOKUP(A{excel_row},\'Running Finance\'!$A$5:$E$100000,4,FALSE),"")',
            money6,
        )

        tr += 1

    last_tx_row = tr - 1
    if last_tx_row >= 4:
        tx_ws.autofilter(3, 0, last_tx_row, 7)

        tx_ws.conditional_format(
            4, 0, last_tx_row, 0, {"type": "formula", "criteria": "=MOD(ROW(),2)=0", "format": stripe_date}
        )
        tx_ws.conditional_format(
            4, 1, last_tx_row, 1, {"type": "formula", "criteria": "=MOD(ROW(),2)=0", "format": stripe_text}
        )
        tx_ws.conditional_format(
            4, 2, last_tx_row, 4, {"type": "formula", "criteria": "=MOD(ROW(),2)=0", "format": stripe_money2}
        )
        tx_ws.conditional_format(
            4, 5, last_tx_row, 5, {"type": "formula", "criteria": "=MOD(ROW(),2)=0", "format": stripe_text}
        )
        tx_ws.conditional_format(
            4, 6, last_tx_row, 6, {"type": "formula", "criteria": "=MOD(ROW(),2)=0", "format": stripe_money2}
        )
        tx_ws.conditional_format(
            4, 7, last_tx_row, 7, {"type": "formula", "criteria": "=MOD(ROW(),2)=0", "format": stripe_money6}
        )

        # Totals line (principal / markup / amount)
        total_row = last_tx_row + 1
        last_excel = last_tx_row + 1
        tx_ws.write(total_row, 0, "Totals", total_label)
        tx_ws.write_blank(total_row, 1, None, total_label)
        tx_ws.write_formula(total_row, 2, f"=SUM(C5:C{last_excel})", total_money2)
        tx_ws.write_formula(total_row, 3, f"=SUM(D5:D{last_excel})", total_money2)
        tx_ws.write_formula(total_row, 4, f"=SUM(E5:E{last_excel})", total_money2)
        tx_ws.write_blank(total_row, 5, None, total_label)
        tx_ws.write_blank(total_row, 6, None, total_label)
        tx_ws.write_blank(total_row, 7, None, total_label)

        tx_ws.set_landscape()
        tx_ws.fit_to_pages(1, 0)

    # ----------------------------
    # Sheet 4: Monthly Summary (month-by-month)
    # ----------------------------
    month_ws = wb.add_worksheet("Monthly Summary")
    month_ws.set_column(0, 0, 10)  # Month
    month_ws.set_column(1, 3, 18)  # principals
    month_ws.set_column(4, 5, 18)  # markups
    month_ws.set_column(6, 6, 12)  # avg rate
    month_ws.set_column(7, 7, 10)  # days
    month_ws.set_column(8, 8, 18)  # markup postings

    month_ws.write(0, 0, "Bank", meta_label)
    month_ws.write(0, 1, bank.name, meta_value)
    month_ws.write(1, 0, "Loan", meta_label)
    month_ws.write(1, 1, loan.name, meta_value)
    month_ws.write(2, 0, "Range", meta_label)
    month_ws.write(2, 1, f"{start} to {end}", subtle)

    m_headers = [
        "Month",
        "Opening Principal",
        "Closing Principal",
        "Principal Δ",
        "Daily Markup (sum)",
        "Accrued Markup (end)",
        "Avg Rate %",
        "Days",
        "Markup Postings (sum)",
    ]
    month_ws.set_row(3, 18)
    for c, h in enumerate(m_headers):
        month_ws.write(3, c, h, header)
    month_ws.freeze_panes(4, 1)

    # Aggregate from ledger rows
    by_month: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for row in rows:
        by_month[_month_key(row["date"])].append(row)

    # Aggregate markup postings from transactions
    markup_post_by_month: dict[tuple[int, int], float] = defaultdict(float)
    for t in txs:
        if (t.category or "").lower() == "markup":
            markup_post_by_month[_month_key(t.date)] += float(t.amount)

    months = sorted(by_month.keys())
    mr = 4
    for (yy, mm) in months:
        mrows = by_month[(yy, mm)]
        mrows.sort(key=lambda x: x["date"])
        opening = float(mrows[0]["principal_balance"])
        closing = float(mrows[-1]["principal_balance"])
        principal_delta = closing - opening
        daily_markup_sum = float(sum(rw["daily_markup"] for rw in mrows))
        accrued_end = float(mrows[-1]["accrued_markup"])
        avg_rate = float(sum(rw["rate_percent"] for rw in mrows) / max(len(mrows), 1))
        days = len(mrows)
        postings = float(markup_post_by_month.get((yy, mm), 0.0))

        month_ws.write(mr, 0, f"{yy:04d}-{mm:02d}", text_cell)
        month_ws.write_number(mr, 1, opening, money2)
        month_ws.write_number(mr, 2, closing, money2)
        month_ws.write_number(mr, 3, principal_delta, money2)
        month_ws.write_number(mr, 4, daily_markup_sum, money6)
        month_ws.write_number(mr, 5, accrued_end, money6)
        month_ws.write_number(mr, 6, avg_rate, rate4)
        month_ws.write_number(mr, 7, days, int0)
        month_ws.write_number(mr, 8, postings, money2)
        mr += 1

    last_m_row = mr - 1
    if last_m_row >= 4:
        month_ws.autofilter(3, 0, last_m_row, 8)

        month_ws.conditional_format(
            4, 0, last_m_row, 0, {"type": "formula", "criteria": "=MOD(ROW(),2)=0", "format": stripe_text}
        )
        month_ws.conditional_format(
            4, 1, last_m_row, 3, {"type": "formula", "criteria": "=MOD(ROW(),2)=0", "format": stripe_money2}
        )
        month_ws.conditional_format(
            4, 4, last_m_row, 5, {"type": "formula", "criteria": "=MOD(ROW(),2)=0", "format": stripe_money6}
        )
        month_ws.conditional_format(
            4, 6, last_m_row, 6, {"type": "formula", "criteria": "=MOD(ROW(),2)=0", "format": stripe_rate4}
        )
        month_ws.conditional_format(
            4, 7, last_m_row, 7, {"type": "formula", "criteria": "=MOD(ROW(),2)=0", "format": stripe_int0}
        )
        month_ws.conditional_format(
            4, 8, last_m_row, 8, {"type": "formula", "criteria": "=MOD(ROW(),2)=0", "format": stripe_money2}
        )

        # Totals row (sum-only where it makes sense)
        total_row = last_m_row + 1
        last_excel = last_m_row + 1
        month_ws.write(total_row, 0, "Totals", total_label)
        month_ws.write_blank(total_row, 1, None, total_label)
        month_ws.write_blank(total_row, 2, None, total_label)
        month_ws.write_formula(total_row, 3, f"=SUM(D5:D{last_excel})", total_money2)
        month_ws.write_formula(total_row, 4, f"=SUM(E5:E{last_excel})", total_money6)
        month_ws.write_blank(total_row, 5, None, total_label)
        month_ws.write_blank(total_row, 6, None, total_label)
        month_ws.write_formula(total_row, 7, f"=SUM(H5:H{last_excel})", int0)
        month_ws.write_formula(total_row, 8, f"=SUM(I5:I{last_excel})", total_money2)

        month_ws.set_landscape()
        month_ws.fit_to_pages(1, 0)

    wb.close()