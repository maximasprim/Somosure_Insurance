"""A small workbook that reproduces the quirks of the real weekly report, for the import tests.

Built with openpyxl, so formulas have no saved results - which also exercises the importer's own
evaluation of the sheet's commission / tax formulas.
"""

import io
from datetime import datetime

from openpyxl import Workbook

HEADERS = [
    "START DATE", "EXPIRY DATE", "CLIENT NAME", "UNDERWRITER", "REG NO", "DATE PAID", "STAFF NAME/BRANCH",
    "NEW BUSINESS/RENEWAL", "POLICY NUMBER", "PREMIUM PAID", "GROSS COMMISSION", "WITHHOLDING TAX", "EXP REVENUE",
]


def _header(ws, row, month):
    ws.cell(row, 1, month)
    for i, title in enumerate(HEADERS, start=2):
        ws.cell(row, i, title)


def _dates(ws, row, start, expiry):
    for col, value in ((2, start), (3, expiry)):
        cell = ws.cell(row, col, value)
        if isinstance(value, datetime):
            cell.number_format = "mm/dd/yyyy"  # how the real sheet displays them: month first


def _money(ws, row, premium, rate):
    ws.cell(row, 11, premium)
    ws.cell(row, 12, f"={rate}%*K{row}")
    ws.cell(row, 13, f"=L{row}*10%")
    ws.cell(row, 14, f"=L{row}-M{row}")


def build_workbook(*, premium_jan=50000, include_second_row=True, include_february=True, include_year_typo=False, include_no_premium=False) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "2026 Sales"

    _header(ws, 1, "JANUARY")
    # Excel stored these day/month dates month-first: 6 Jan 2026 became 1 June, 5 Jan 2027 became 1 May.
    _dates(ws, 2, datetime(2026, 6, 1), datetime(2027, 5, 1))
    ws.cell(2, 4, "JOHN DOE")
    ws.cell(2, 5, "MORNACH")
    ws.cell(2, 6, "KDR 904V")
    ws.cell(2, 7, "07/01/2026")
    ws.cell(2, 8, "JOSPHINE -HQ")
    ws.cell(2, 9, "RENEWAL")
    ws.cell(2, 10, 123456.0)
    _money(ws, 2, premium_jan, 10)

    last = 2
    if include_second_row:
        _dates(ws, 3, "13/01/2026", "12/01/2027")
        ws.cell(3, 4, "JANE ROE")
        ws.cell(3, 5, "DIRECTLINE")
        ws.cell(3, 6, "PI")  # a product, not a plate
        ws.cell(3, 7, "13/01/2026")
        ws.cell(3, 8, "HQ-JOSEPHINE")
        ws.cell(3, 9, "NEW BUSINESS")
        ws.cell(3, 10, "HDO/1/2026 (COMP)")
        _money(ws, 3, 20000, 20)
        last = 3
    ws.cell(last + 1, 12, f"=K{last + 1}*10%")  # leftover formula, no client
    ws.cell(last + 2, 11, f"=SUM(K2:K{last})")
    ws.cell(last + 2, 12, f"=SUM(L2:L{last})")

    if include_february:
        # header without a month name; the month is on the first data row
        _header(ws, 8, None)
        _dates(ws, 9, datetime(2026, 3, 2), datetime(2027, 2, 2))
        ws.cell(9, 1, "FEBRUARY")
        ws.cell(9, 4, "PETER KAMAU")
        ws.cell(9, 5, "KENYAN ALLIANCE")
        ws.cell(9, 6, "KDM 813Y")
        ws.cell(9, 7, "03/02/2026")
        ws.cell(9, 8, "Wilson - Ruiru")
        ws.cell(9, 10, "ABC/999")
        _money(ws, 9, 30000, 10)

    if include_february and include_year_typo:
        # start typed with the wrong year: expiry looks like it is before the start
        _dates(ws, 10, "14/03/2027", "13/03/2027")
        ws.cell(10, 4, "ANN WANJIRU")
        ws.cell(10, 5, "CIC")
        ws.cell(10, 6, "KDA 100A")
        ws.cell(10, 7, "14/03/2026")
        ws.cell(10, 8, "Wilson - Ruiru")
        ws.cell(10, 10, "TYPO/1")
        _money(ws, 10, 10000, 10)

    if include_february and include_no_premium:
        _dates(ws, 11, "10/02/2026", "09/02/2027")
        ws.cell(11, 4, "NO PREMIUM")
        ws.cell(11, 5, "MONARCH")
        ws.cell(11, 6, "KBB 111B")
        ws.cell(11, 7, "10/02/2026")
        ws.cell(11, 8, "Wilson - Ruiru")
        ws.cell(11, 10, "NP/1")  # no premium on this row

    claims = wb.create_sheet("Claims 2026")
    for i, title in enumerate(["Client Name", "Client Contact", "Car number plate/policy", "underwritter", "Date reported", "status", "Action"], start=1):
        claims.cell(2, i, title)  # header on row 2, like the real 2023/2024 sheets
    claims.cell(3, 1, "JOHN DOE")
    claims.cell(3, 2, 721559694)
    claims.cell(3, 3, "KDR 904V")
    claims.cell(3, 4, "MORNACH")
    claims.cell(3, 5, datetime(2026, 3, 5)).number_format = "mm/dd/yyyy"
    claims.cell(3, 6, "Claim reported on 03/05/2026. Documents submitted on 04/05/2026. Release letter issued on 20/05/2026.")
    claims.cell(3, 7, "Closed")

    ipf = wb.create_sheet("IPF REPORT 2026")
    for i, title in enumerate(["INSURANCE", "DETAILS", "DATE PAID", "AMOUNT"], start=1):
        ipf.cell(1, i, title)
    ipf.cell(2, 1, "MONARCH")
    ipf.cell(2, 2, "BIDII CREDIT KCZ 021")
    ipf.cell(2, 3, datetime(2026, 3, 2)).number_format = "mm/dd/yyyy"
    ipf.cell(2, 4, 20090)
    ipf.cell(3, 1, "MONARCH")
    ipf.cell(3, 2, "PETER GACAGUA")
    ipf.cell(3, 3, "23/02/2026")
    ipf.cell(3, 4, 37569)

    wb.create_sheet("Notes").cell(1, 1, "not a data sheet")

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
