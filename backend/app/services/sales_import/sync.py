"""Decides, for one upload, what is new, what changed, what stayed the same and what vanished.

Pure: works on plain dicts (rows from the importer, rows already in the ledger), so the rules
that matter most for "the system follows the sheet" can be tested without a database.

Matching, in order:
 1. natural key (insurer + policy number + sheet year, or the whole-row key when there is no number);
 2. fallback key (insurer + plate + start date + premium + client) against rows nothing else matched -
    this is how a row that gained a policy number, or moved to another sheet, is recognised as the
    same row instead of one disappearing and another appearing.

A row in the ledger that no row in the upload matches is "missing from sheet" - kept, marked, and
brought back to active if it reappears. It is only judged for years whose sheet is in the upload,
so uploading just the 2026 sheet never touches 2025.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Callable, Iterable

SALES_TRACKED = [
    "client_name", "phone", "underwriter", "reg_no", "asset_ref", "product_line", "start_date", "expiry_date",
    "date_paid", "staff_name", "branch", "business_type", "policy_number", "cover_type", "premium", "commission",
    "wht", "net_revenue", "period_year", "period_month",
]
CLAIM_TRACKED = ["client_name", "contact", "reg_or_policy", "underwriter", "date_reported", "narrative", "outcome"]
IPF_TRACKED = ["underwriter", "details", "date_paid", "amount"]


@dataclass
class Matched:
    id: Any
    values: dict[str, Any]
    diffs: list[dict[str, str | None]]
    restored: bool  # was "missing from sheet", is back


@dataclass
class SyncPlan:
    inserts: list[dict[str, Any]] = field(default_factory=list)
    matched: list[Matched] = field(default_factory=list)
    missing_ids: list[Any] = field(default_factory=list)

    @property
    def updated(self) -> list[Matched]:
        return [m for m in self.matched if m.diffs]

    @property
    def unchanged(self) -> list[Matched]:
        return [m for m in self.matched if not m.diffs]

    @property
    def restored(self) -> list[Matched]:
        return [m for m in self.matched if m.restored]


def _norm(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"))
    if isinstance(value, float):
        return Decimal(str(value)).quantize(Decimal("0.01"))
    if isinstance(value, str):
        return value.strip() or None
    return value


def differs(old: Any, new: Any) -> bool:
    return _norm(old) != _norm(new)


def show(value: Any) -> str | None:
    value = _norm(value)
    if value is None:
        return None
    if isinstance(value, date):
        return f"{value:%d/%m/%Y}"
    return str(value)


# Flags that an accepted date fix resolves.
FIX_RESOLVES = {"expiry_before_start", "period_over_a_year"}
# Corrections kept as overrides: these are dates; anything else in an override (a phone number) is plain text.
DATE_OVERRIDES = {"start_date", "expiry_date"}


def level_of(flags: list[dict[str, Any]]) -> str:
    severities = {f.get("severity") for f in flags}
    for level in ("error", "warning", "info"):
        if level in severities:
            return level
    return "none"


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if isinstance(value, date) else str(value)


def apply_overrides(row: dict[str, Any], overrides: dict[str, dict[str, str]]) -> tuple[dict[str, Any], dict[str, dict[str, str]]]:
    """Fixes a person accepted stay in place for as long as the sheet still holds the value they
    corrected (`ov["sheet"]`). The moment the sheet cell changes - fixed there, or changed to
    something else - the sheet wins again and the override is dropped. -> (row, overrides kept)."""
    row = dict(row)
    kept: dict[str, dict[str, str]] = {}
    for field_name, ov in overrides.items():
        if _iso(row.get(field_name)) == ov.get("sheet"):
            row[field_name] = date.fromisoformat(ov["value"]) if field_name in DATE_OVERRIDES else ov["value"]
            kept[field_name] = ov
    if any(f in DATE_OVERRIDES for f in kept):
        flags = [f for f in row.get("flags") or [] if f.get("code") not in FIX_RESOLVES]
        for field_name, ov in kept.items():
            if field_name not in DATE_OVERRIDES:
                continue
            label = "start date" if field_name == "start_date" else "expiry date"
            flags.append({
                "code": "fix_applied", "severity": "info",
                "message": f"The {label} in the sheet ({_fmt_iso(ov['sheet'])}) was changed to {_fmt_iso(ov['value'])} when a suggested fix was accepted. "
                           "Correct it in the sheet and this note goes away.",
            })
        row["flags"] = flags
        row["issue_level"] = level_of(flags)
    return row, kept


def _fmt_iso(value: str) -> str:
    y, m, d = value.split("-")
    return f"{d}/{m}/{y}"


def plan_sync(
    new_rows: list[dict[str, Any]],
    existing: Iterable[dict[str, Any]],
    *,
    tracked: list[str],
    year_field: str,
    uploaded_years: set[int],
    use_fallback: bool = False,
    in_scope: Callable[[dict[str, Any]], bool] | None = None,
    overrides: bool = False,
) -> SyncPlan:
    existing = list(existing)
    by_key = {e["natural_key"]: e for e in existing}
    claimed: set[Any] = set()
    matches: list[dict[str, Any] | None] = [None] * len(new_rows)

    for i, row in enumerate(new_rows):
        e = by_key.get(row["natural_key"])
        if e is not None and e["id"] not in claimed:
            matches[i] = e
            claimed.add(e["id"])

    if use_fallback:
        by_fallback: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for e in existing:
            if e["id"] not in claimed and e.get("fallback_key"):
                by_fallback[e["fallback_key"]].append(e)
        for i, row in enumerate(new_rows):
            if matches[i] is None:
                for e in by_fallback.get(row.get("fallback_key"), []):
                    if e["id"] not in claimed:
                        matches[i] = e
                        claimed.add(e["id"])
                        break

    plan = SyncPlan()
    for row, e in zip(new_rows, matches):
        if e is None:
            plan.inserts.append(row)
            continue
        if overrides:
            row, kept = apply_overrides(row, e.get("overrides") or {})
            row["overrides"] = kept or None
        diffs = [
            {"field": f, "old": show(e.get(f)), "new": show(row.get(f))}
            for f in tracked if differs(e.get(f), row.get(f))
        ]
        plan.matched.append(Matched(id=e["id"], values=row, diffs=diffs, restored=e.get("status") == "missing_from_sheet"))

    for e in existing:
        if e["id"] in claimed or e.get("status") != "active":
            continue
        scoped = in_scope(e) if in_scope else e.get(year_field) in uploaded_years
        if scoped:
            plan.missing_ids.append(e["id"])
    return plan


def best_sales_match(claim: dict[str, Any], sales: list[dict[str, Any]]) -> Any | None:
    """Which sale a claim belongs to: same plate, preferring the same insurer and the policy
    that was running on the day it was reported. None when nothing fits well enough."""
    reg = claim.get("reg_no")
    if not reg:
        return None
    candidates = [s for s in sales if s.get("reg_no") == reg]
    if not candidates:
        return None
    reported = claim.get("date_reported")

    def score(s: dict[str, Any]) -> float:
        points = 0.0
        if s.get("underwriter") and s["underwriter"] == claim.get("underwriter"):
            points += 2
        if reported and s.get("start_date") and s.get("expiry_date") and s["start_date"] <= reported <= s["expiry_date"]:
            points += 3
        elif reported and s.get("start_date"):
            points -= abs((reported - s["start_date"]).days) / 365
        return points

    best = max(candidates, key=score)
    return best["id"] if score(best) > 0 else None
