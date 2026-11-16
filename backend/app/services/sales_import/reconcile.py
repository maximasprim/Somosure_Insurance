"""Month-by-month check of the sheet's own SUM rows against the rows underneath them.

The system always works from the rows. The sheet's totals are only compared, never
trusted: in the real file some SUM ranges stop short of the last row (e.g. January
2025's commission total covers rows 3-18 while its premium total covers 3-23).
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Iterable

from app.services.sales_import.parser import BlockTotals, SalesRecord

TOLERANCE = Decimal("1.00")
ZERO = Decimal("0")


def reconcile(blocks: Iterable[BlockTotals], records: Iterable[SalesRecord]) -> list[dict]:
    sums: dict[tuple, dict[str, Decimal | int]] = defaultdict(
        lambda: {"rows": 0, "premium": ZERO, "commission": ZERO, "wht": ZERO, "net": ZERO}
    )
    for r in records:
        s = sums[(r.sheet, r.period_year, r.period_month)]
        s["rows"] += 1
        s["premium"] += r.premium or ZERO
        s["commission"] += r.commission or ZERO
        s["wht"] += r.wht or ZERO
        s["net"] += r.net_revenue or ZERO

    out: list[dict] = []
    for b in blocks:
        s = sums.get((b.sheet, b.year, b.month), {"rows": 0, "premium": ZERO, "commission": ZERO, "wht": ZERO, "net": ZERO})
        pairs = {
            "premium": (s["premium"], b.sheet_premium),
            "commission": (s["commission"], b.sheet_commission),
            "wht": (s["wht"], b.sheet_wht),
            "net": (s["net"], b.sheet_net),
        }
        diffs = {k: (calc - sheet) for k, (calc, sheet) in pairs.items() if sheet is not None and abs(calc - sheet) > TOLERANCE}
        if b.total_row is None:
            status = "no_total"
        elif diffs:
            status = "mismatch"
        else:
            status = "ok"
        out.append({
            "sheet": b.sheet, "year": b.year, "month": b.month, "rows": s["rows"],
            "premium": s["premium"], "commission": s["commission"], "wht": s["wht"], "net": s["net"],
            "sheet_premium": b.sheet_premium, "sheet_commission": b.sheet_commission,
            "sheet_wht": b.sheet_wht, "sheet_net": b.sheet_net,
            "difference": diffs, "status": status,
            "total_row": b.total_row,
        })
    out.sort(key=lambda d: (d["sheet"], d["year"], d["month"] or 0))
    return out
