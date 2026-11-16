"""Builds the cleaned workbook: the same layout the team already uses, with the repairs applied.

* One sheet per year ("2026 Sales"), month blocks with a header row and a SUM row, columns A-N
  exactly as before. Two optional columns are added at the end (O = COVER TYPE, P = PHONE NO);
  the importer reads them if present and does not need them.
* Dates are real dates (shown dd/mm/yyyy), so Excel can no longer swap day and month.
* Staff / branch is written one way ("Josphine - HQ"), underwriters one way ("MONARCH").
* "Claims YYYY" and "IPF REPORT YYYY" sheets in the same style, and a "Review" sheet listing
  rows that still need a look. The importer ignores "Review".

Pure: takes plain dicts, returns bytes.
"""

from __future__ import annotations

import io
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any, Iterable

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.services.sales_import.cleaners import MONTH_NAMES

SALES_COLUMNS = [
    ("START DATE", 13), ("EXPIRY DATE", 13), ("CLIENT NAME", 30), ("UNDERWRITER", 16), ("REG NO", 14),
    ("DATE PAID", 13), ("STAFF NAME/BRANCH", 24), ("NEW BUSINESS/RENEWAL", 16), ("POLICY NUMBER", 24),
    ("PREMIUM PAID", 14), ("GROSS COMMISSION", 16), ("WITHHOLDING TAX", 15), ("EXP REVENUE", 14),
    ("COVER TYPE", 11), ("PHONE NO", 15),
]
DATE_FMT = "dd/mm/yyyy"
MONEY_FMT = "#,##0.00"
HEADER_FILL = PatternFill("solid", fgColor="FFE699")
BOLD = Font(bold=True)
BUSINESS_LABEL = {"new_business": "NEW BUSINESS", "renewal": "RENEWAL"}
OUTCOME_LABEL = {"closed": "Closed", "closed_unresponsive": "Closed, client unresponsive", "action_needed": "Action", "open": ""}


def _num(value: Any) -> float | None:
    return float(value) if value is not None else None


def _staff_label(entry: dict) -> str | None:
    name, branch = entry.get("staff_name"), entry.get("branch")
    if name and branch:
        return f"{name} - {branch}"
    return name or branch


def _write_sales_sheet(wb: Workbook, year: int, entries: list[dict]) -> None:
    ws = wb.create_sheet(f"{year} Sales")
    ws.freeze_panes = "B2"
    for idx, (_, width) in enumerate(SALES_COLUMNS, start=2):
        ws.column_dimensions[get_column_letter(idx)].width = width
    ws.column_dimensions["A"].width = 12

    blocks: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for e in entries:
        blocks[(e["period_year"], e["period_month"] or 0)].append(e)

    row = 1
    for (_, month), rows in sorted(blocks.items()):
        ws.cell(row, 1, MONTH_NAMES[month - 1] if month else "").font = BOLD
        for idx, (title, _) in enumerate(SALES_COLUMNS, start=2):
            c = ws.cell(row, idx, title)
            c.font, c.fill = BOLD, HEADER_FILL
            c.alignment = Alignment(wrap_text=True, vertical="center")
        ws.cell(row, 1).fill = HEADER_FILL
        first = row + 1
        for e in sorted(rows, key=lambda x: (x.get("date_paid") or date.min, x.get("sheet_row") or 0)):
            row += 1
            values = [
                e.get("start_date"), e.get("expiry_date"), e.get("client_name"), e.get("underwriter"),
                e.get("reg_no") or e.get("asset_ref"), e.get("date_paid"), _staff_label(e),
                BUSINESS_LABEL.get(e.get("business_type") or ""), e.get("policy_number"),
                _num(e.get("premium")), _num(e.get("commission")), _num(e.get("wht")), _num(e.get("net_revenue")),
                e.get("cover_type"), e.get("phone"),
            ]
            for idx, value in enumerate(values, start=2):
                cell = ws.cell(row, idx, value)
                if isinstance(value, date):
                    cell.number_format = DATE_FMT
                elif idx in (11, 12, 13, 14):
                    cell.number_format = MONEY_FMT
            # Keep the sheet's habit of live formulas where the stored figure is exactly what the formula gives.
            commission, wht, net = e.get("commission"), e.get("wht"), e.get("net_revenue")
            if commission is not None and wht is not None and abs(wht - (commission * Decimal("0.1")).quantize(Decimal("0.01"))) <= Decimal("0.01"):
                ws.cell(row, 13, f"=ROUND(L{row}*10%,2)").number_format = MONEY_FMT
                if net is not None and abs(net - (commission - wht)) <= Decimal("0.01"):
                    ws.cell(row, 14, f"=L{row}-M{row}").number_format = MONEY_FMT
        last = row
        row += 1
        ws.cell(row, 4, "TOTAL").font = BOLD
        for col in (11, 12, 13, 14):
            letter = get_column_letter(col)
            c = ws.cell(row, col, f"=SUM({letter}{first}:{letter}{last})")
            c.font, c.number_format = BOLD, MONEY_FMT
        row += 2


def _write_claims_sheet(wb: Workbook, year: int, claims: list[dict]) -> None:
    ws = wb.create_sheet(f"Claims {year}")
    headers = ["Client Name", "Client Contact", "Car number plate/policy", "Underwriter", "Date reported", "Status", "Action"]
    widths = [28, 16, 22, 14, 14, 90, 24]
    for idx, (title, width) in enumerate(zip(headers, widths), start=1):
        c = ws.cell(1, idx, title)
        c.font, c.fill = BOLD, HEADER_FILL
        ws.column_dimensions[get_column_letter(idx)].width = width
    ws.freeze_panes = "A2"
    for r, claim in enumerate(sorted(claims, key=lambda x: (x.get("date_reported") or date.min)), start=2):
        values = [claim.get("client_name"), claim.get("contact"), claim.get("reg_or_policy"), claim.get("underwriter"),
                  claim.get("date_reported"), claim.get("narrative"), OUTCOME_LABEL.get(claim.get("outcome") or "", "")]
        for idx, value in enumerate(values, start=1):
            cell = ws.cell(r, idx, value)
            if isinstance(value, date):
                cell.number_format = DATE_FMT
            if idx == 6:
                cell.alignment = Alignment(wrap_text=True, vertical="top")


def _write_ipf_sheet(wb: Workbook, year: int, rows: list[dict]) -> None:
    ws = wb.create_sheet(f"IPF REPORT {year}")
    for idx, (title, width) in enumerate([("INSURANCE", 16), ("DETAILS", 34), ("DATE PAID", 13), ("AMOUNT", 14)], start=1):
        c = ws.cell(1, idx, title)
        c.font, c.fill = BOLD, HEADER_FILL
        ws.column_dimensions[get_column_letter(idx)].width = width
    for r, item in enumerate(sorted(rows, key=lambda x: (x.get("date_paid") or date.min)), start=2):
        ws.cell(r, 1, item.get("underwriter"))
        ws.cell(r, 2, item.get("details"))
        c = ws.cell(r, 3, item.get("date_paid"))
        c.number_format = DATE_FMT
        c = ws.cell(r, 4, _num(item.get("amount")))
        c.number_format = MONEY_FMT


def _write_review_sheet(wb: Workbook, issues: list[dict]) -> None:
    ws = wb.create_sheet("Review")
    headers = ["Sheet", "Month", "Client", "Policy number", "Severity", "Issue"]
    widths = [14, 12, 30, 24, 10, 100]
    for idx, (title, width) in enumerate(zip(headers, widths), start=1):
        c = ws.cell(1, idx, title)
        c.font, c.fill = BOLD, HEADER_FILL
        ws.column_dimensions[get_column_letter(idx)].width = width
    for r, issue in enumerate(issues, start=2):
        for idx, key in enumerate(["sheet", "month", "client_name", "policy_number", "severity", "message"], start=1):
            ws.cell(r, idx, issue.get(key))


def build_cleaned_workbook(sales: Iterable[dict], claims: Iterable[dict], ipf: Iterable[dict],
                           issues: Iterable[dict], years: list[int] | None = None) -> bytes:
    sales, claims, ipf, issues = list(sales), list(claims), list(ipf), list(issues)
    wb = Workbook()
    wb.remove(wb.active)
    wanted = sorted(set(years or {e["sheet_year"] for e in sales} | {c["period_year"] for c in claims} | {i["period_year"] for i in ipf}), reverse=True)
    for year in wanted:
        _write_sales_sheet(wb, year, [e for e in sales if e["sheet_year"] == year])
        _write_claims_sheet(wb, year, [c for c in claims if c["period_year"] == year])
        ipf_rows = [i for i in ipf if i["period_year"] == year]
        if ipf_rows:
            _write_ipf_sheet(wb, year, ipf_rows)
    if issues:
        _write_review_sheet(wb, issues)
    if not wb.sheetnames:
        wb.create_sheet("Empty")
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
