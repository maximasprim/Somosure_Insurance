"""Which pricing tier applies to a financing request - pure Python, no database.

A tier says "for a loan of THIS size over THIS many months, the monthly interest rate
is X". Tiers are set up by staff (financing settings), so nothing here hard-codes a
number. The rules, in one place:

  * Amount ranges are FROM-inclusive and UP-TO-exclusive, so back-to-back tiers
    (0-100,000, 100,000-500,000) meet cleanly with no gap and no double-count.
  * Term ranges are inclusive at both ends (3-6 months, 7-10 months). A blank upper
    limit means "no upper limit".
  * A tier can be for everyone ("all"), or only individuals, or only companies.
  * If several tiers match, one written for the applicant's own kind beats one for
    "all", then the narrower amount range wins, then the narrower term range - so a
    specific tier always beats a general one. (Overlapping tiers of the same kind are
    refused when they are saved, so ties between those can't normally happen.)
  * The existing-customer concession rate is decided before tiers are consulted and is
    never overridden by one - see check_eligibility.
"""

from decimal import Decimal
from typing import Any, Iterable

APPLIES_TO = ("all", "individual", "corporate")
_INF = Decimal("Infinity")


def _num(value: Any) -> Decimal:
    return Decimal(str(value))


def _amount_hi(tier: Any) -> Decimal:
    return _INF if tier.max_amount is None else _num(tier.max_amount)


def _term_hi(tier: Any) -> float:
    return float("inf") if tier.max_term_months is None else float(tier.max_term_months)


def applicant_kind(is_corporate: bool) -> str:
    return "corporate" if is_corporate else "individual"


def matches(tier: Any, amount: Any, term_months: int, is_corporate: bool) -> bool:
    if not tier.is_active:
        return False
    if tier.applies_to not in ("all", applicant_kind(is_corporate)):
        return False
    amount = _num(amount)
    if not (_num(tier.min_amount) <= amount < _amount_hi(tier)):
        return False
    return float(tier.min_term_months) <= term_months <= _term_hi(tier)


def find_tier(tiers: Iterable[Any], amount: Any, term_months: int, is_corporate: bool) -> Any | None:
    candidates = [t for t in tiers if matches(t, amount, term_months, is_corporate)]
    if not candidates:
        return None
    kind = applicant_kind(is_corporate)

    def specificity(t: Any):
        return (
            0 if t.applies_to == kind else 1,
            _amount_hi(t) - _num(t.min_amount),
            _term_hi(t) - float(t.min_term_months),
            str(getattr(t, "label", "")).lower(),
            str(getattr(t, "id", "")),
        )

    return min(candidates, key=specificity)


def overlaps(a: Any, b: Any) -> bool:
    """Two active tiers for the same kind of applicant that could both claim the same
    loan - the situation staff must resolve before saving."""
    if not (a.is_active and b.is_active) or a.applies_to != b.applies_to:
        return False
    amount_overlap = _num(a.min_amount) < _amount_hi(b) and _num(b.min_amount) < _amount_hi(a)
    term_overlap = float(a.min_term_months) <= _term_hi(b) and float(b.min_term_months) <= _term_hi(a)
    return amount_overlap and term_overlap


def describe(tier: Any) -> str:
    """A readable one-line summary, for messages and the admin screen."""
    low = f"KES {_num(tier.min_amount):,.0f}"
    high = "no upper limit" if tier.max_amount is None else f"under KES {_num(tier.max_amount):,.0f}"
    terms = (
        f"{tier.min_term_months}+ months"
        if tier.max_term_months is None
        else f"{tier.min_term_months}-{tier.max_term_months} months"
    )
    return f"{low} to {high}, {terms}"
