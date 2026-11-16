"""Reads the weekly report workbook into plain records.

What it has to cope with (all of it present in the real file):

* One sheet per year ("2026 Sales", "2025 sales"), made of month blocks: a header row,
  the rows, then a SUM row. Headers are spelled differently from block to block.
* A block whose header row has no month name (the month sits on the first data row), or
  whose month name is on a line of its own above the header.
* A sheet that starts in the previous year's November (the "2023 sales" sheet).
* Columns that come and go between years (phone number, new-business/renewal).
* Totals rows, leftover formulas on otherwise empty rows, and sheet ranges that run
  hundreds of rows past the real data - none of which are data.
* Columns the app has never seen: they are kept on the row's `raw` and reported, not lost.

Nothing here touches the database. It returns `ParsedWorkbook`.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from app.services.sales_import import claims as claims_mod
from app.services.sales_import.cleaners import (
    ERROR,
    INFO,
    WARNING,
    ExactDate,
    Flag,
    clean_business_type,
    date_readings,
    clean_display,
    clean_phone,
    classify_asset,
    day_first_format,
    clean_plate,
    clean_policy_number,
    looks_like_plate,
    month_from_label,
    norm_text,
    resolve_policy_dates,
    resolve_sequential_date,
    to_money,
)

# --------------------------------------------------------------------------------------
# Header vocabulary (normalised: upper-case, letters only, single spaces)
# --------------------------------------------------------------------------------------

SALES_HEADERS: dict[str, str] = {
    "START DATE": "start_date",
    "EXPIRY DATE": "expiry_date",
    "CLIENT NAME": "client_name",
    "CLIENT": "client_name",
    "PHONE NO": "phone",
    "PHONE": "phone",
    "PHONE NUMBER": "phone",
    "CONTACT": "phone",
    "UNDERWRITER": "underwriter",
    "UNDERWRITTER": "underwriter",
    "INSURER": "underwriter",
    "REG NO": "reg_no",
    "REG NUMBER": "reg_no",
    "REGISTRATION": "reg_no",
    "REG": "reg_no",
    "DATE PAID": "date_paid",
    "STAFF NAME BRANCH": "staff_branch",
    "STAFF NAME": "staff_branch",
    "STAFF": "staff_branch",
    "NEW BUSINESS RENEWAL": "business_type",
    "NEW BUINESS RENEWAL": "business_type",
    "NEW BUSINESS": "business_type",
    "BUSINESS TYPE": "business_type",
    "POLICY NUMBER": "policy_no",
    "POLICY NO": "policy_no",
    "COVER TYPE": "cover_type",
    "COVER": "cover_type",
    "PREMIUM PAID": "premium",
    "PREMIUM": "premium",
    "GROSS COMMISSION": "commission",
    "GROSS COMMISSIO": "commission",
    "COMMISSION": "commission",
    "WITHHOLDING TAX": "wht",
    "WHT": "wht",
    "EXP REVENUE": "net_revenue",
    "EXPECTED REVENUE": "net_revenue",
    "NET REVENUE": "net_revenue",
}
CLAIM_HEADERS: dict[str, str] = {
    "CLIENT NAME": "client_name",
    "CLIENT CONTACT": "contact",
    "CONTACT": "contact",
    "CAR NUMBER PLATE POLICY": "reg_or_policy",
    "CAR NUMBER PLATE": "reg_or_policy",
    "REG NO": "reg_or_policy",
    "UNDERWRITTER": "underwriter",
    "UNDERWRITER": "underwriter",
    "DATE REPORTED": "date_reported",
    "STATUS": "narrative",
    "ACTION": "outcome",
}
IPF_HEADERS: dict[str, str] = {
    "INSURANCE": "underwriter",
    "UNDERWRITER": "underwriter",
    "INSURER": "underwriter",
    "DETAILS": "details",
    "DATE PAID": "date_paid",
    "AMOUNT": "amount",
}

MIN_HEADER_MATCHES = {"sales": 5, "claims": 4, "ipf": 3}


def _header_key(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z]+", " ", value.upper())).strip()


def map_headers(cells: list[Any], vocabulary: dict[str, str]) -> dict[int, str]:
    """Column index -> field for a header row; empty when the row is not a header."""
    mapping: dict[int, str] = {}
    seen: set[str] = set()
    for idx, cell in enumerate(cells):
        field_name = vocabulary.get(_header_key(cell))
        if field_name and field_name not in seen:
            mapping[idx] = field_name
            seen.add(field_name)
    return mapping


# --------------------------------------------------------------------------------------
# Records
# --------------------------------------------------------------------------------------


@dataclass
class BlockTotals:
    """One month block and what the sheet's own SUM row said about it."""
    sheet: str
    year: int
    month: int | None
    header_row: int
    total_row: int | None = None
    sheet_premium: Decimal | None = None
    sheet_commission: Decimal | None = None
    sheet_wht: Decimal | None = None
    sheet_net: Decimal | None = None


@dataclass
class SalesRecord:
    sheet: str
    sheet_year: int
    row: int
    period_year: int
    period_month: int | None
    client_name: str
    phone: str | None
    underwriter_raw: str | None
    plate: str | None
    product_line: str
    asset_ref: str | None
    start_date: date | None
    expiry_date: date | None
    date_paid: date | None
    staff_raw: str | None
    business_type: str | None
    policy_number: str | None
    cover_type: str | None
    premium: Decimal | None
    commission: Decimal | None
    wht: Decimal | None
    net_revenue: Decimal | None
    flags: list[Flag] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ClaimRecord:
    sheet: str
    sheet_year: int
    row: int
    client_name: str
    contact: str | None
    reg_or_policy: str | None
    plate: str | None
    underwriter_raw: str | None
    date_reported: date | None
    narrative: str | None
    outcome_raw: str | None
    outcome: str
    milestones: list[dict[str, str]]
    flags: list[Flag] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class IpfRecord:
    sheet: str
    sheet_year: int
    row: int
    underwriter_raw: str | None
    details: str | None
    date_paid: date | None
    amount: Decimal | None
    flags: list[Flag] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class SheetInfo:
    name: str
    kind: str  # sales | claims | ipf
    year: int
    rows: int = 0


@dataclass
class ParsedWorkbook:
    sales: list[SalesRecord] = field(default_factory=list)
    claims: list[ClaimRecord] = field(default_factory=list)
    ipf: list[IpfRecord] = field(default_factory=list)
    blocks: list[BlockTotals] = field(default_factory=list)
    sheets: list[SheetInfo] = field(default_factory=list)
    ignored_sheets: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    unknown_columns: dict[str, list[str]] = field(default_factory=dict)


class WorkbookError(ValueError):
    """The file could not be read as a workbook at all."""


# --------------------------------------------------------------------------------------
# Formula handling - the sheet stores commission/tax as formulas
# --------------------------------------------------------------------------------------

_PCT_TIMES_REF = re.compile(r"^=\s*(\d+(?:\.\d+)?)\s*%\s*\*\s*\$?([A-Z]{1,2})\$?(\d+)\s*$")
_REF_TIMES_PCT = re.compile(r"^=\s*\$?([A-Z]{1,2})\$?(\d+)\s*\*\s*(\d+(?:\.\d+)?)\s*%\s*$")
_ROUND_PCT = re.compile(r"^=\s*ROUND\(\s*\$?([A-Z]{1,2})\$?(\d+)\s*\*\s*(\d+(?:\.\d+)?)\s*%\s*,\s*\d\s*\)\s*$", re.I)
_REF_MINUS_REF = re.compile(r"^=\s*\$?([A-Z]{1,2})\$?(\d+)\s*-\s*\$?([A-Z]{1,2})\$?(\d+)\s*$")


def _evaluate(formula: str, row: int, numbers: dict[str, Decimal | None]) -> Decimal | None:
    """Evaluates the three formula shapes the sheet uses when Excel did not save a result
    (e.g. a file produced by another tool). Anything else -> None."""
    m = _PCT_TIMES_REF.match(formula)
    if m and int(m.group(3)) == row and numbers.get(m.group(2)) is not None:
        return to_money(Decimal(m.group(1)) / 100 * numbers[m.group(2)])
    m = _REF_TIMES_PCT.match(formula)
    if m and int(m.group(2)) == row and numbers.get(m.group(1)) is not None:
        return to_money(Decimal(m.group(3)) / 100 * numbers[m.group(1)])
    m = _ROUND_PCT.match(formula)
    if m and int(m.group(2)) == row and numbers.get(m.group(1)) is not None:
        return to_money(Decimal(m.group(3)) / 100 * numbers[m.group(1)])
    m = _REF_MINUS_REF.match(formula)
    if m and int(m.group(2)) == row and int(m.group(4)) == row:
        a, b = numbers.get(m.group(1)), numbers.get(m.group(3))
        if a is not None and b is not None:
            return to_money(a - b)
    return None


def _rows(ws, min_row: int = 1) -> list[list[Any]]:
    """Cell values row by row, with true dates in day-first / month-name cells marked as exact."""
    rows: list[list[Any]] = []
    for row in ws.iter_rows(min_row=min_row):
        values: list[Any] = []
        for cell in row:
            value = cell.value
            if isinstance(value, (datetime, date)) and day_first_format(cell.number_format):
                value = ExactDate(value.year, value.month, value.day)
            values.append(value)
        rows.append(values)
    return rows


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


# --------------------------------------------------------------------------------------
# Sheet classification
# --------------------------------------------------------------------------------------


def classify_sheet(name: str) -> tuple[str, int] | None:
    year = re.search(r"\b(20\d{2})\b", name)
    if not year:
        return None
    upper = name.upper()
    if "CLAIM" in upper:
        return "claims", int(year.group(1))
    if "IPF" in upper:
        return "ipf", int(year.group(1))
    if "SALES" in upper:
        return "sales", int(year.group(1))
    return None


# --------------------------------------------------------------------------------------
# Sales sheets
# --------------------------------------------------------------------------------------


@dataclass
class _Block:
    month: int | None
    header_row: int
    colmap: dict[int, str]
    month_inferred: bool = False
    total: BlockTotals | None = None
    rows: list["_RawRow"] = field(default_factory=list)


@dataclass
class _RawRow:
    number: int
    formulas: dict[str, Any]
    values: dict[str, Any]
    letters: dict[str, str]  # field -> column letter


def _assign_period_years(blocks: list[_Block], sheet_year: int) -> list[int]:
    """A sheet that opens in November/December and later reaches January starts in the
    previous year (the real '2023 sales' sheet opens with November and December 2022)."""
    years = [sheet_year] * len(blocks)
    first_jan = next((i for i, b in enumerate(blocks) if b.month == 1), None)
    if first_jan:
        for i in range(first_jan):
            if blocks[i].month and blocks[i].month >= 7:
                years[i] = sheet_year - 1
    return years


def _read_sales_sheet(ws_f, ws_v, sheet: str, year: int, out: ParsedWorkbook) -> int:
    blocks: list[_Block] = []
    current: _Block | None = None
    pending_month: int | None = None
    ignored = 0

    for row_no, (frow, vrow) in enumerate(zip(_rows(ws_f), ws_v.iter_rows(values_only=True)), start=1):
        f, v = frow, list(vrow)
        if all(x is None or (isinstance(x, str) and not x.strip()) for x in f):
            continue

        mapping = map_headers(f, SALES_HEADERS)
        if len(mapping) >= MIN_HEADER_MATCHES["sales"] and "client_name" in mapping.values():
            month = month_from_label(f[0]) or pending_month
            current = _Block(month=month, header_row=row_no, colmap=mapping)
            blocks.append(current)
            pending_month = None
            known = set(SALES_HEADERS)
            for idx, cell in enumerate(f):
                if idx not in mapping and isinstance(cell, str) and cell.strip() and _header_key(cell) not in known and idx > 0:
                    out.unknown_columns.setdefault(sheet, []).append(cell.strip())
            continue

        # A line holding only a month name ("APRIL") sitting above the header row.
        if month_from_label(f[0]) and all(x is None for x in f[1:]):
            pending_month = month_from_label(f[0])
            continue
        if current is None:
            continue

        cm = current.colmap
        client_idx = next(i for i, name in cm.items() if name == "client_name")
        client = clean_display(f[client_idx] if client_idx < len(f) else None)
        if client and norm_text(client) in {"TOTAL", "TOTALS", "GRAND TOTAL"}:
            client = None  # a labelled totals row

        if client is None:
            prem_i = next((i for i, n in cm.items() if n == "premium"), None)
            comm_i = next((i for i, n in cm.items() if n == "commission"), None)
            is_total = any(
                isinstance(f[i], str) and f[i].upper().startswith("=SUM")
                for i in (prem_i, comm_i) if i is not None and i < len(f)
            )
            if is_total:
                def cached(name: str) -> Decimal | None:
                    idx = next((i for i, n in cm.items() if n == name), None)
                    return to_money(v[idx]) if idx is not None and idx < len(v) else None
                current.total = BlockTotals(sheet, year, current.month, current.header_row, row_no,
                                            cached("premium"), cached("commission"), cached("wht"), cached("net_revenue"))
            else:
                ignored += 1
            continue

        # The month name sits on the first data row when the header row had none.
        if current.month is None and month_from_label(f[0]):
            current.month = month_from_label(f[0])

        letters = {name: get_column_letter(i + 1) for i, name in cm.items()}
        current.rows.append(_RawRow(
            number=row_no,
            formulas={name: (f[i] if i < len(f) else None) for i, name in cm.items()},
            values={name: (v[i] if i < len(v) else None) for i, name in cm.items()},
            letters=letters,
        ))

    # A block with no month name anywhere (header, line above, first data row) is the month
    # after the block before it.
    for i, block in enumerate(blocks):
        if block.month is None and i > 0 and blocks[i - 1].month:
            block.month, block.month_inferred = blocks[i - 1].month % 12 + 1, True
    years = _assign_period_years(blocks, year)
    total_rows = 0
    for block, period_year in zip(blocks, years):
        totals = block.total or BlockTotals(sheet, year, block.month, block.header_row)
        totals.year, totals.month = period_year, block.month
        out.blocks.append(totals)
        for raw in block.rows:
            out.sales.append(_build_sales_record(raw, sheet, year, period_year, block.month, block.month_inferred))
            total_rows += 1
    if ignored:
        out.notes.append(f"{sheet}: {ignored} leftover row(s) with no client name were ignored")
    return total_rows


def _numbers_for_formulas(raw: _RawRow) -> dict[str, Decimal | None]:
    """Column letter -> the number in that column on this row (cached result preferred)."""
    numbers: dict[str, Decimal | None] = {}
    for name in ("premium", "commission", "wht", "net_revenue"):
        if name not in raw.letters:
            continue
        cached, formula = raw.values.get(name), raw.formulas.get(name)
        numbers[raw.letters[name]] = to_money(cached if cached is not None else (None if isinstance(formula, str) else formula))
    return numbers


def _build_sales_record(raw: _RawRow, sheet: str, sheet_year: int, period_year: int, month: int | None,
                        month_inferred: bool) -> SalesRecord:
    flags: list[Flag] = []
    f, v = raw.formulas, raw.values
    if month_inferred:
        flags.append(Flag("month_inferred", INFO, "The month block had no month name; it was worked out from the block before it"))

    # money ------------------------------------------------------------------
    numbers = _numbers_for_formulas(raw)
    premium = to_money(v.get("premium") if v.get("premium") is not None else f.get("premium"))
    if premium is None:
        shown = f.get("premium")
        if shown is None:
            flags.append(Flag("premium_missing", ERROR, "No premium on this row"))
        else:
            flags.append(Flag("premium_not_a_number", ERROR, f"Premium cell holds '{shown}', not an amount"))
    elif premium <= 0:
        flags.append(Flag("premium_not_positive", ERROR, f"Premium is {premium}"))

    def money_field(name: str) -> Decimal | None:
        cached, formula = v.get(name), f.get(name)
        number = to_money(cached) if cached is not None else None
        if number is None and isinstance(formula, str) and formula.startswith("="):
            number = _evaluate(formula, raw.number, numbers)
        if number is None and not isinstance(formula, str):
            number = to_money(formula)
        if name in raw.letters:
            numbers[raw.letters[name]] = number  # later formulas on this row can build on it
        return number

    commission = money_field("commission")
    wht = money_field("wht")
    net = money_field("net_revenue")
    if "commission" in raw.letters:
        if commission is None or commission == 0:
            flags.append(Flag("commission_missing_or_zero", WARNING, "Commission is empty or zero"))
        elif premium and commission / premium > Decimal("0.30"):
            flags.append(Flag("commission_over_30pct", WARNING, f"Commission is {commission / premium:.0%} of the premium"))

    # dates ------------------------------------------------------------------
    block = (period_year, month) if month else None
    resolved = resolve_policy_dates(f.get("start_date"), f.get("expiry_date"), f.get("date_paid"), block)
    flags.extend(resolved.flags)

    # identifiers ------------------------------------------------------------
    policy_number, cover_type = clean_policy_number(f.get("policy_no"))
    cover_cell = clean_display(f.get("cover_type"))
    if cover_cell:
        cover_type = cover_cell.upper()
    if not policy_number and "policy_no" in raw.letters:
        flags.append(Flag("policy_number_missing", WARNING, "No policy number"))
    product_line, plate, asset_ref = classify_asset(f.get("reg_no"))
    if product_line == "unknown":
        flags.append(Flag("reg_missing", WARNING, "No registration number or product on this row"))
    elif product_line == "other":
        flags.append(Flag("reg_unusual", INFO, f"'{asset_ref}' is not a number plate or a known product"))
    elif product_line == "motor" and asset_ref:
        flags.append(Flag("reg_unusual", INFO, f"'{asset_ref}' does not look like a valid Kenyan number plate"))

    business = clean_business_type(f.get("business_type"))
    if "business_type" in raw.letters and business is None:
        flags.append(Flag("business_type_missing", INFO, "New business / renewal not filled in"))

    phone_cell = f.get("phone")
    phone = clean_phone(phone_cell)
    if phone_cell not in (None, "") and phone is None:
        flags.append(Flag("phone_unreadable", INFO, f"Phone '{phone_cell}' could not be read as a Kenyan number"))

    return SalesRecord(
        sheet=sheet, sheet_year=sheet_year, row=raw.number, period_year=period_year, period_month=month,
        client_name=clean_display(f.get("client_name")) or "",
        phone=phone,
        underwriter_raw=clean_display(f.get("underwriter")),
        plate=plate, product_line=product_line, asset_ref=asset_ref,
        start_date=resolved.start, expiry_date=resolved.expiry, date_paid=resolved.paid,
        staff_raw=clean_display(f.get("staff_branch")),
        business_type=business, policy_number=policy_number, cover_type=cover_type,
        premium=premium, commission=commission, wht=wht, net_revenue=net,
        flags=flags,
        raw={k: _json_safe(val) for k, val in f.items() if val is not None},
    )


# --------------------------------------------------------------------------------------
# Claims and IPF sheets
# --------------------------------------------------------------------------------------


def _find_header(ws_f, vocabulary: dict[str, str], minimum: int) -> tuple[int, dict[int, str]] | None:
    for row_no, row in enumerate(ws_f.iter_rows(min_row=1, max_row=min(ws_f.max_row, 15), values_only=True), start=1):
        mapping = map_headers(list(row), vocabulary)
        if len(mapping) >= minimum:
            return row_no, mapping
    return None


def _read_claims_sheet(ws_f, ws_v, sheet: str, year: int, out: ParsedWorkbook) -> int:
    found = _find_header(ws_f, CLAIM_HEADERS, MIN_HEADER_MATCHES["claims"])
    if not found:
        out.notes.append(f"{sheet}: no claims header row found - sheet skipped")
        return 0
    header_row, cm = found
    count, previous = 0, None
    for row_no, row in enumerate(_rows(ws_f, header_row + 1), start=header_row + 1):
        cells = {name: (row[i] if i < len(row) else None) for i, name in cm.items()}
        client = clean_display(cells.get("client_name"))
        if not client:
            continue
        narrative = clean_display(cells.get("narrative"))
        milestones = claims_mod.extract_milestones(narrative)
        flags: list[Flag] = []

        reported, date_flags = _resolve_reported(cells.get("date_reported"), milestones, previous)
        flags.extend(date_flags)
        if reported is None:
            flags.append(Flag("date_missing", WARNING, "No readable date reported"))
        else:
            previous = reported

        reg_cell = clean_display(cells.get("reg_or_policy"))
        plate = clean_plate(reg_cell)[0] if looks_like_plate(reg_cell) else None
        outcome_raw = clean_display(cells.get("outcome"))
        outcome = claims_mod.normalize_outcome(outcome_raw, narrative)
        contact = clean_phone(cells.get("contact"))
        if cells.get("contact") not in (None, "", "-") and contact is None:
            flags.append(Flag("phone_unreadable", INFO, f"Contact '{cells.get('contact')}' could not be read as a Kenyan number"))
        out.claims.append(ClaimRecord(
            sheet=sheet, sheet_year=year, row=row_no, client_name=client, contact=contact,
            reg_or_policy=reg_cell, plate=plate, underwriter_raw=clean_display(cells.get("underwriter")),
            date_reported=reported, narrative=narrative, outcome_raw=outcome_raw, outcome=outcome,
            milestones=milestones, flags=flags,
            raw={k: _json_safe(val) for k, val in cells.items() if val is not None},
        ))
        count += 1
    return count


def _resolve_reported(cell: Any, milestones: list[dict[str, str]], previous: date | None) -> tuple[date | None, list[Flag]]:
    """Reported date: the cell, with day/month order settled by the dates in the narrative
    (the claim cannot have been reported after it was assessed)."""
    readings = date_readings(cell)
    if not readings:
        return None, []
    earliest = None
    if milestones:
        earliest = min(date.fromisoformat(m["date"]) for m in milestones)
    reported_text = next((date.fromisoformat(m["date"]) for m in milestones if m["event"] == "reported"), None)
    best, best_score = readings[0], -99.0
    for reading in readings:
        score = 0.5 if reading.swapped else 0.0
        if reported_text and reading.value == reported_text:
            score += 3
        if earliest:
            gap = (earliest - reading.value).days
            if 0 <= gap <= 120:
                score += 2
            elif gap < 0:
                score -= 2
        if previous and reading.value >= previous:
            score += 0.25
        if score > best_score:
            best, best_score = reading, score
    flags = []
    if best.swapped:
        flags.append(Flag("date_day_month_swapped", INFO, f"Date reported was stored as {cell:%d/%m/%Y} and read as {best.value:%d/%m/%Y}"
                          if isinstance(cell, (date, datetime)) else "Date reported day/month swapped"))
    return best.value, flags


def _read_ipf_sheet(ws_f, ws_v, sheet: str, year: int, out: ParsedWorkbook) -> int:
    found = _find_header(ws_f, IPF_HEADERS, MIN_HEADER_MATCHES["ipf"])
    if not found:
        out.notes.append(f"{sheet}: no IPF header row found - sheet skipped")
        return 0
    header_row, cm = found
    count, previous = 0, None
    for row_no, row in enumerate(_rows(ws_f, header_row + 1), start=header_row + 1):
        cells = {name: (row[i] if i < len(row) else None) for i, name in cm.items()}
        details = clean_display(cells.get("details"))
        amount = to_money(cells.get("amount"))
        if not details and amount is None:
            continue
        flags: list[Flag] = []
        paid, date_flags = resolve_sequential_date(cells.get("date_paid"), previous)
        flags.extend(date_flags)
        if paid:
            previous = paid
        else:
            flags.append(Flag("date_missing", WARNING, "No readable date paid"))
        if amount is None:
            flags.append(Flag("amount_missing", ERROR, "No amount on this row"))
        out.ipf.append(IpfRecord(
            sheet=sheet, sheet_year=year, row=row_no, underwriter_raw=clean_display(cells.get("underwriter")),
            details=details, date_paid=paid, amount=amount, flags=flags,
            raw={k: _json_safe(val) for k, val in cells.items() if val is not None},
        ))
        count += 1
    return count


# --------------------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------------------


def parse_workbook(data: bytes) -> ParsedWorkbook:
    try:
        wb_formulas = load_workbook(io.BytesIO(data), data_only=False)
        wb_values = load_workbook(io.BytesIO(data), data_only=True)
    except Exception as exc:  # openpyxl raises several unrelated types for a bad file
        raise WorkbookError("That file could not be opened as an Excel workbook (.xlsx).") from exc

    out = ParsedWorkbook()
    for name in wb_formulas.sheetnames:
        kind = classify_sheet(name)
        if kind is None:
            out.ignored_sheets.append(name)
            continue
        sheet_kind, year = kind
        ws_f, ws_v = wb_formulas[name], wb_values[name]
        reader = {"sales": _read_sales_sheet, "claims": _read_claims_sheet, "ipf": _read_ipf_sheet}[sheet_kind]
        rows = reader(ws_f, ws_v, name, year, out)
        out.sheets.append(SheetInfo(name=name, kind=sheet_kind, year=year, rows=rows))
    if not out.sheets:
        raise WorkbookError("No sheets named like '2026 Sales', 'Claims 2026' or 'IPF REPORT 2026' were found in this file.")
    return out
