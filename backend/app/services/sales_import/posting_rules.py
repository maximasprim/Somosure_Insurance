"""Rules for turning a workbook row into the system's own records (customer, quote request, quote,
application, policy, payment). Pure - no database - so every rule can be tested on the real file.

The principle: append everything that can be appended, and flag what is missing instead of refusing.
A row is only held back when the system genuinely cannot store it:

  * no premium            - a policy and its payment need an amount;
  * no start AND no expiry - a policy needs dates;
  * underwriter not linked - a policy needs an insurer (link it on the Post to system tab).

Everything else is appended with a flag: no phone (customer saved with a blank phone), no policy number
(a placeholder is used until the sheet has the real one), one missing date (the other plus or minus a year
is used and marked as assumed).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from hashlib import sha1
from typing import Any

from dateutil.relativedelta import relativedelta

# The REG NO column's product -> the system's quote category (free text in the quote request).
CATEGORY_BY_PRODUCT = {
    "motor": "motor", "medical": "medical", "life": "life", "credit_life": "life", "travel": "travel",
    "property": "property", "personal_accident": "personal_accident", "wiba": "wiba",
    "professional_indemnity": "professional_indemnity", "bid_bond": "bid_bond",
}


def category_for(product_line: str | None) -> str:
    return CATEGORY_BY_PRODUCT.get(product_line or "", "other")


def short_hash(natural_key: str, size: int = 12) -> str:
    return sha1(natural_key.encode()).hexdigest()[:size].upper()


def sold_on(entry: dict[str, Any]) -> date:
    """The day the sale is recorded against: the date paid, else the start, else the first of the sheet's month."""
    return entry.get("date_paid") or entry.get("start_date") or date(entry["period_year"], entry.get("period_month") or 1, 1)


def policy_status(end: date, today: date) -> str:
    return "active" if end >= today else "expired"


def derive_dates(start: date | None, expiry: date | None) -> tuple[date | None, date | None, bool]:
    """-> (start, end, assumed). One missing date is derived from the other as a one-year policy and marked
    assumed; both missing -> (None, None, False), and the row is held for review."""
    if start and expiry:
        return start, expiry, False
    if start:
        return start, start + relativedelta(years=1) - timedelta(days=1), True
    if expiry:
        return expiry - relativedelta(years=1) + timedelta(days=1), expiry, True
    return None, None, False


def placeholder_policy_number(natural_key: str, sheet_year: int) -> str:
    return f"WB-{sheet_year}-{short_hash(natural_key, 8)}"


def is_placeholder(policy_number: str | None) -> bool:
    return bool(policy_number) and policy_number.startswith("WB-") and policy_number.count("-") == 2


def unique_policy_number(entry: dict[str, Any], taken: set[str]) -> tuple[str, str | None]:
    """-> (number to use, flag code or None). The sheet's own number when it is free; otherwise the number with
    the sheet year added (the same number legitimately returns on a renewal); with no number, a placeholder."""
    preferred = entry.get("policy_number")
    if not preferred:
        number = placeholder_policy_number(entry["natural_key"], entry["sheet_year"])
        return number, "policy_number_placeholder"
    preferred = preferred[:50]
    if preferred not in taken:
        return preferred, None
    with_year = f"{preferred}-{entry['sheet_year']}"[:50]
    if with_year not in taken:
        return with_year, "policy_number_year_added"
    return f"{preferred[:36]}-{entry['sheet_year']}-{short_hash(entry['natural_key'], 6)}"[:50], "policy_number_year_added"


@dataclass
class Classification:
    ready: bool
    reasons: list[tuple[str, str]] = field(default_factory=list)  # why it is held
    flags: list[dict[str, str]] = field(default_factory=list)  # what to review once it is appended


HELD_LABELS = {
    "no_provider_link": "Underwriter not linked to a provider",
    "no_underwriter": "No underwriter on the row",
    "missing_premium": "No premium",
    "missing_dates": "No start or expiry date",
}


def classify(entry: dict[str, Any], linked: set[str]) -> Classification:
    """Can this ledger row be appended now, and what should be reviewed when it is?"""
    reasons: list[tuple[str, str]] = []
    underwriter = entry.get("underwriter")
    if not underwriter:
        reasons.append(("no_underwriter", HELD_LABELS["no_underwriter"]))
    elif underwriter not in linked:
        reasons.append(("no_provider_link", f"{underwriter} is not linked to a provider yet"))
    premium = entry.get("premium")
    if premium is None or premium <= 0:
        reasons.append(("missing_premium", HELD_LABELS["missing_premium"]))
    start, end, assumed = derive_dates(entry.get("start_date"), entry.get("expiry_date"))
    if start is None:
        reasons.append(("missing_dates", HELD_LABELS["missing_dates"]))
    if reasons:
        return Classification(False, reasons)

    flags: list[dict[str, str]] = []
    if not entry.get("phone"):
        flags.append({"code": "customer_no_phone", "message": "No phone number - the customer was saved with a blank phone"})
    if not entry.get("policy_number"):
        flags.append({"code": "policy_number_placeholder", "message": "No policy number in the sheet - a placeholder is used until it has one"})
    if assumed:
        which = "expiry" if entry.get("expiry_date") is None else "start"
        flags.append({"code": "date_assumed", "message": f"The {which} date is missing in the sheet - one year from the other date is used"})
    if entry.get("issue_level") in ("warning", "error"):
        flags.append({"code": "import_issues", "message": "The sheet row has problems flagged on the Ledger tab"})
    if entry.get("date_paid") is None:
        flags.append({"code": "payment_date_assumed", "message": "No date paid in the sheet - the sale month is used for the payment date"})
    return Classification(True, [], flags)
