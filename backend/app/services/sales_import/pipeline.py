"""Turns a ParsedWorkbook into rows ready for the database.

Resolves names (underwriters, staff, branches), builds the keys that let the next upload
recognise the same rows, flags rows that repeat, and gathers every flag into one issue list.
Still pure: saved aliases come in as plain dicts, nothing is written anywhere.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from hashlib import sha1
from typing import Any

from app.services.sales_import.cleaners import (
    INFO,
    WARNING,
    Flag,
    StaffResolver,
    norm_text,
    resolve_underwriter,
    row_keys,
)
from app.services.sales_import.parser import ParsedWorkbook


@dataclass
class ResolvedWorkbook:
    sales: list[dict[str, Any]] = field(default_factory=list)
    claims: list[dict[str, Any]] = field(default_factory=list)
    ipf: list[dict[str, Any]] = field(default_factory=list)
    issues: list[dict[str, Any]] = field(default_factory=list)  # warnings and errors, one line each
    issue_counts: dict[str, dict[str, Any]] = field(default_factory=dict)  # code -> {severity, count}
    new_underwriter_aliases: dict[str, tuple[str, str]] = field(default_factory=dict)  # key -> (canonical, as typed)
    new_staff_aliases: dict[str, tuple[str | None, str | None, str]] = field(default_factory=dict)


def _suffix_duplicates(keys: list[str]) -> list[tuple[str, int]]:
    """Same key twice in one upload -> the second gets '#2' so both rows are kept."""
    seen: Counter[str] = Counter()
    out = []
    for key in keys:
        seen[key] += 1
        n = seen[key]
        out.append((key if n == 1 else sha1(f"{key}#{n}".encode()).hexdigest(), n))
    return out


def _disambiguate(primary: list[str], fallback: list[str]) -> list[tuple[str, bool]]:
    """Rows that share a primary key (same insurer + policy number in one year's sheet) get keys
    built from the whole row instead, so they are told apart by what they contain, never by the
    order they happen to sit in. Fully identical rows are numbered. -> [(key, was_shared)]."""
    groups: dict[str, list[int]] = defaultdict(list)
    for i, key in enumerate(primary):
        groups[key].append(i)
    out: list[tuple[str, bool]] = [(k, False) for k in primary]
    used: Counter[str] = Counter()
    for key, members in groups.items():
        if len(members) == 1:
            continue
        for i in members:
            candidate = sha1(f"{key}|{fallback[i]}".encode()).hexdigest()
            used[candidate] += 1
            n = used[candidate]
            out[i] = (candidate if n == 1 else sha1(f"{candidate}#{n}".encode()).hexdigest(), True)
    return out


def _level(flags: list[Flag]) -> str:
    severities = {f.severity for f in flags}
    for level in ("error", "warning", "info"):
        if level in severities:
            return level
    return "none"


def _count(resolved: ResolvedWorkbook, flags: list[Flag]) -> None:
    for f in flags:
        slot = resolved.issue_counts.setdefault(f.code, {"severity": f.severity, "count": 0})
        slot["count"] += 1


def _issue(resolved: ResolvedWorkbook, flag: Flag, *, sheet: str, row: int, month: int | None, client: str | None, policy: str | None) -> None:
    if flag.severity == INFO:
        return
    resolved.issues.append({
        "severity": flag.severity, "code": flag.code, "sheet": sheet, "row": row, "month": month,
        "client_name": client, "policy_number": policy, "message": flag.message,
    })


def resolve_workbook(
    pw: ParsedWorkbook,
    underwriter_aliases: dict[str, str] | None = None,
    staff_aliases: dict[str, tuple[str | None, str | None]] | None = None,
) -> ResolvedWorkbook:
    out = ResolvedWorkbook()
    staff = StaffResolver((r.staff_raw for r in pw.sales), staff_aliases)

    # ---- sales ---------------------------------------------------------------------------
    pending: list[dict[str, Any]] = []
    for rec in pw.sales:
        flags = list(rec.flags)
        underwriter, uw_flags = resolve_underwriter(rec.underwriter_raw, underwriter_aliases)
        flags.extend(uw_flags)
        if rec.underwriter_raw:
            key = norm_text(rec.underwriter_raw)
            if underwriter and underwriter != key and key not in (underwriter_aliases or {}):
                out.new_underwriter_aliases.setdefault(key, (underwriter, rec.underwriter_raw))
        staff_name, branch, st_flags = staff.resolve(rec.staff_raw)
        flags.extend(st_flags)

        primary, fallback = row_keys(underwriter, rec.policy_number, rec.plate or rec.asset_ref, rec.start_date, rec.premium, rec.client_name, rec.sheet_year)
        rate = None
        if rec.premium and rec.premium > 0 and rec.commission is not None:
            rate = (rec.commission / rec.premium).quantize(Decimal("0.0001"))
        pending.append({
            "_primary": primary,
            "fallback_key": fallback,
            "sheet_name": rec.sheet, "sheet_year": rec.sheet_year, "sheet_row": rec.row,
            "period_year": rec.period_year, "period_month": rec.period_month,
            "client_name": rec.client_name, "client_key": norm_text(rec.client_name), "phone": rec.phone,
            "underwriter_raw": rec.underwriter_raw, "underwriter": underwriter,
            "reg_no": rec.plate, "asset_ref": rec.asset_ref, "product_line": rec.product_line,
            "start_date": rec.start_date, "expiry_date": rec.expiry_date, "date_paid": rec.date_paid,
            "staff_raw": rec.staff_raw, "staff_name": staff_name, "branch": branch,
            "business_type": rec.business_type, "policy_number": rec.policy_number, "cover_type": rec.cover_type,
            "premium": rec.premium, "commission": rec.commission, "wht": rec.wht, "net_revenue": rec.net_revenue,
            "commission_rate": rate, "_flags": flags, "raw": rec.raw,
        })

    # An insurer's usual rate, so unusual ones are called out (not corrected).
    rates: dict[str, list[Decimal]] = defaultdict(list)
    for p in pending:
        if p["underwriter"] and p["commission_rate"] and p["commission_rate"] > 0:
            rates[p["underwriter"]].append(p["commission_rate"].quantize(Decimal("0.005")))
    usual = {uw: Counter(vals).most_common(1)[0][0] for uw, vals in rates.items() if len(vals) >= 5}
    for p in pending:
        rate, base = p["commission_rate"], usual.get(p["underwriter"])
        if rate and base and abs(rate - base) > Decimal("0.005") and rate <= Decimal("0.30"):
            p["_flags"].append(Flag("commission_rate_differs", INFO,
                                    f"Commission is {rate:.1%} of the premium; {p['underwriter']} is usually {base:.1%}"))

    for p, (key, shared) in zip(pending, _disambiguate([p["_primary"] for p in pending], [p["fallback_key"] for p in pending])):
        p["natural_key"] = key
        if shared:
            p["_flags"].append(Flag("duplicate_in_sheet", INFO,
                                    "The same insurer and policy number (or an identical row) appears again in this year's sheet - kept as a separate row (endorsement or repeat?)"))
    for p in pending:
        flags: list[Flag] = p.pop("_flags")
        p.pop("_primary")
        _count(out, flags)
        for f in flags:
            _issue(out, f, sheet=p["sheet_name"], row=p["sheet_row"], month=p["period_month"], client=p["client_name"], policy=p["policy_number"])
        p["flags"] = [f.as_dict() for f in flags]
        p["issue_level"] = _level(flags)
        out.sales.append(p)

    # ---- claims --------------------------------------------------------------------------
    claim_rows = []
    for c in pw.claims:
        underwriter, uw_flags = resolve_underwriter(c.underwriter_raw, underwriter_aliases)
        flags = list(c.flags) + uw_flags
        key = sha1("|".join([norm_text(underwriter), norm_text(c.client_name), c.plate or norm_text(c.reg_or_policy),
                             c.date_reported.isoformat() if c.date_reported else ""]).encode()).hexdigest()
        claim_rows.append((c, underwriter, flags, key))
    for (c, underwriter, flags, _), (key, n) in zip(claim_rows, _suffix_duplicates([r[3] for r in claim_rows])):
        if n > 1:
            flags.append(Flag("duplicate_in_sheet", WARNING, "Identical claim row appears more than once"))
        _count(out, flags)
        for f in flags:
            _issue(out, f, sheet=c.sheet, row=c.row, month=None, client=c.client_name, policy=c.reg_or_policy)
        out.claims.append({
            "natural_key": key, "sheet_name": c.sheet, "sheet_row": c.row, "period_year": c.sheet_year,
            "client_name": c.client_name, "client_key": norm_text(c.client_name), "contact": c.contact,
            "reg_or_policy": c.reg_or_policy, "reg_no": c.plate, "underwriter_raw": c.underwriter_raw,
            "underwriter": underwriter, "date_reported": c.date_reported, "narrative": c.narrative,
            "outcome_raw": c.outcome_raw, "outcome": c.outcome, "milestones": c.milestones,
            "flags": [f.as_dict() for f in flags], "issue_level": _level(flags), "raw": c.raw,
        })

    # ---- IPF -----------------------------------------------------------------------------
    ipf_rows = []
    for i in pw.ipf:
        underwriter, uw_flags = resolve_underwriter(i.underwriter_raw, underwriter_aliases)
        flags = list(i.flags) + uw_flags
        key = sha1("|".join([str(i.sheet_year), norm_text(underwriter), norm_text(i.details),
                             i.date_paid.isoformat() if i.date_paid else "", f"{i.amount:.2f}" if i.amount is not None else ""]).encode()).hexdigest()
        ipf_rows.append((i, underwriter, flags, key))
    for (i, underwriter, flags, _), (key, n) in zip(ipf_rows, _suffix_duplicates([r[3] for r in ipf_rows])):
        if n > 1:
            flags.append(Flag("duplicate_in_sheet", WARNING, "Identical IPF row appears more than once"))
        _count(out, flags)
        for f in flags:
            _issue(out, f, sheet=i.sheet, row=i.row, month=None, client=i.details, policy=None)
        out.ipf.append({
            "natural_key": key, "sheet_name": i.sheet, "sheet_row": i.row, "period_year": i.sheet_year,
            "underwriter_raw": i.underwriter_raw, "underwriter": underwriter, "details": i.details,
            "date_paid": i.date_paid, "amount": i.amount, "flags": [f.as_dict() for f in flags],
            "issue_level": _level(flags), "raw": i.raw,
        })

    out.new_staff_aliases = dict(staff.resolved)
    return out
