"""Choosing which part of the workbook to import ("from January 2025 onward").

Applied to the parsed workbook before anything else, so counts, problems, month-total checks
and the names it learns all describe only the chosen period, and rows outside it are left
completely alone in the system (never updated, never marked missing).
"""

from __future__ import annotations

import re
from typing import Any

from app.services.sales_import.parser import ParsedWorkbook

Period = tuple[int, int]  # (year, month)


def parse_period(text: str | None) -> Period | None:
    """'2025-01' -> (2025, 1). Empty -> None (no limit)."""
    if not text:
        return None
    m = re.fullmatch(r"\s*(\d{4})-(0[1-9]|1[0-2])\s*", text)
    if not m:
        raise ValueError("Periods are written like 2025-01 (year-month).")
    return int(m.group(1)), int(m.group(2))


def in_period(year: int, month: int | None, start: Period | None, end: Period | None) -> bool:
    """With no month (a claim or IPF line with no readable date) only the year is compared."""
    if month is None:
        return (start is None or year >= start[0]) and (end is None or year <= end[0])
    return (start is None or (year, month) >= start) and (end is None or (year, month) <= end)


def row_period(row_date: Any, fallback_year: int) -> tuple[int, int | None]:
    return (row_date.year, row_date.month) if row_date else (fallback_year, None)


def apply_period(pw: ParsedWorkbook, start: Period | None, end: Period | None) -> dict[str, int]:
    """Drops everything outside the period from `pw`; returns how many rows were skipped."""
    if start is None and end is None:
        return {"sales": 0, "claims": 0, "ipf": 0}
    skipped = {"sales": 0, "claims": 0, "ipf": 0}

    kept_sales = [r for r in pw.sales if in_period(r.period_year, r.period_month, start, end)]
    skipped["sales"] = len(pw.sales) - len(kept_sales)
    pw.sales = kept_sales
    pw.blocks = [b for b in pw.blocks if b.month is None or in_period(b.year, b.month, start, end)]

    kept_claims = [c for c in pw.claims if in_period(*row_period(c.date_reported, c.sheet_year), start, end)]
    skipped["claims"] = len(pw.claims) - len(kept_claims)
    pw.claims = kept_claims

    kept_ipf = [i for i in pw.ipf if in_period(*row_period(i.date_paid, i.sheet_year), start, end)]
    skipped["ipf"] = len(pw.ipf) - len(kept_ipf)
    pw.ipf = kept_ipf

    counts = {"sales": len(pw.sales), "claims": len(pw.claims), "ipf": len(pw.ipf)}
    for sheet in pw.sheets:
        sheet.rows = sum(
            1 for r in getattr(pw, {"sales": "sales", "claims": "claims", "ipf": "ipf"}[sheet.kind]) if r.sheet == sheet.name
        )
    return skipped
