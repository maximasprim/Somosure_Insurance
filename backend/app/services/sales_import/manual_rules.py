"""A sale typed into the system, shaped exactly like a sheet row.

Pure (no database): turns the form's fields into a ledger row, working out what the sheet works out - the month it
sits in, expiry one year after the start, withholding tax at 10% of commission, net revenue - and validating what
must be right. The row gets the same keys an imported row would, so when the same sale turns up in the weekly
sheet later it is recognised and merged, not duplicated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from dateutil.relativedelta import relativedelta

from app.services.sales_import.cleaners import (
    clean_phone,
    clean_policy_number,
    classify_asset,
    match_branch,
    norm_text,
    row_keys,
)

WHT_RATE = Decimal("0.10")
SHEET_NAME = "Entered in system"
TWO = Decimal("0.01")


def _q(value: Decimal) -> Decimal:
    return value.quantize(TWO, rounding=ROUND_HALF_UP)


@dataclass
class ManualBuild:
    entry: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)


def default_expiry(start: date) -> date:
    """A one-year policy starting 6 Jan 2026 runs to 5 Jan 2027, as in the sheet."""
    return start + relativedelta(years=1) - relativedelta(days=1)


def _title_staff(name: str | None) -> str | None:
    name = (name or "").strip()
    return " ".join(w.capitalize() for w in name.split()) if name else None


def build_manual_entry(p: dict[str, Any], *, underwriter: str, underwriter_name: str) -> ManualBuild:
    """`p` is the form; `underwriter` the canonical name used across the ledger; `underwriter_name` as chosen."""
    errors: list[str] = []
    client = " ".join(str(p.get("client_name") or "").split()).upper()  # the sheet writes names in capitals
    if not client:
        errors.append("Enter the client's name.")

    premium = p.get("premium")
    premium = _q(Decimal(str(premium))) if premium is not None else None
    if premium is None or premium <= 0:
        errors.append("Enter the premium paid (more than zero).")

    start, paid = p.get("start_date"), p.get("date_paid")
    if start is None:
        errors.append("Enter the start date.")
    if paid is None:
        errors.append("Enter the date paid.")
    expiry = p.get("expiry_date") or (default_expiry(start) if start else None)
    if start and expiry and expiry <= start:
        errors.append("The expiry date must be after the start date.")

    phone = None
    if (p.get("phone") or "").strip():
        phone = clean_phone(p["phone"])
        if phone is None:
            errors.append("The phone number is not a Kenyan mobile number (like 0712 345 678).")

    product_line, plate, asset_ref = classify_asset(p.get("reg_or_product"))
    if product_line == "unknown":
        errors.append("Enter the registration number, or the product (PI, WIBA, MEDICAL, CREDIT LIFE...).")

    commission = p.get("commission")
    commission = _q(Decimal(str(commission))) if commission is not None else None
    wht = p.get("wht")
    wht = _q(Decimal(str(wht))) if wht is not None else (_q(commission * WHT_RATE) if commission is not None else None)
    net = _q(commission - wht) if commission is not None and wht is not None else None
    if commission is not None and commission < 0:
        errors.append("Commission cannot be negative.")
    rate = (commission / premium).quantize(Decimal("0.0001")) if commission is not None and premium else None

    if errors:
        return ManualBuild(errors=errors)

    policy_number, cover_from_number = clean_policy_number(p.get("policy_number"))
    cover_type = (p.get("cover_type") or "").strip().upper() or cover_from_number
    staff = _title_staff(p.get("staff_name"))
    branch_text = (p.get("branch") or "").strip()
    branch = match_branch(branch_text) or (branch_text.upper() or None)
    staff_raw = " - ".join(x for x in (staff, branch) if x) or None
    business = {"new_business": "new_business", "renewal": "renewal"}.get(p.get("business_type") or "")

    primary, fallback = row_keys(underwriter, policy_number, plate or asset_ref, start, premium, client, paid.year)
    return ManualBuild(entry={
        "natural_key": primary, "fallback_key": fallback,
        "sheet_name": SHEET_NAME, "sheet_year": paid.year, "sheet_row": None, "period_year": paid.year, "period_month": paid.month,
        "client_name": client, "client_key": norm_text(client), "phone": phone,
        "underwriter_raw": underwriter_name, "underwriter": underwriter,
        "reg_no": plate, "asset_ref": asset_ref, "product_line": product_line,
        "start_date": start, "expiry_date": expiry, "date_paid": paid,
        "staff_raw": staff_raw, "staff_name": staff, "branch": branch, "business_type": business,
        "policy_number": policy_number, "cover_type": cover_type,
        "premium": premium, "commission": commission, "wht": wht, "net_revenue": net, "commission_rate": rate,
        "flags": [], "issue_level": "none", "raw": {"entered_in_system": True}, "status": "active", "origin": "manual",
    })
