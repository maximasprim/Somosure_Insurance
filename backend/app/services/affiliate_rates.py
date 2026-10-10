"""Pure commission maths for the affiliate program (no database, no framework).

Kept separate so the rules that decide how much someone earns can be read - and
tested - on their own.

How the rate for a referral is chosen
-------------------------------------
Admin can set rate RULES. A rule may be tied to one referrer, to one product
category, to a kind of referrer ("an existing customer" or "not yet a
customer"), or any mix - or to none of them (a "for everyone" rule) - and may
only apply between two dates (a promotion). For one referral the best rule wins.
A rule that names the person beats one that names the product, which beats one
that names the kind of referrer:

    this person + product  >  this person  >  product + kind of referrer
        >  product  >  kind of referrer  >  everyone

If no rule applies, the program's rates are used: the "existing customer"
rate if the referrer is an existing customer and one is set, otherwise the
default rate.

Only ACTIVE rules whose dates include today are considered. If two rules are
equally specific, the one created most recently wins - so adding a new rule
is always enough to change what happens next.

"Existing customer" = the referrer has at least one policy with us that is
currently active (not cancelled, not expired).
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Iterable, Optional

CENT = Decimal("0.01")


@dataclass
class RateChoice:
    rate_type: str  # "percent" | "fixed"
    rate_value: Decimal
    max_amount: Optional[Decimal]
    rule_id: Optional[str]
    label: str


def _specificity(rule: Any, referrer_id: Optional[str], category: Optional[str], is_customer: bool) -> int:
    """-1 = rule doesn't apply; otherwise higher = more specific."""
    rule_referrer = str(rule.affiliate_customer_id) if rule.affiliate_customer_id else None
    rule_category = rule.category or None
    rule_segment = getattr(rule, "referrer_segment", None) or None
    if rule_referrer and rule_referrer != (str(referrer_id) if referrer_id else None):
        return -1
    if rule_category and rule_category != category:
        return -1
    if rule_segment == "existing_customer" and not is_customer:
        return -1
    if rule_segment == "not_a_customer" and is_customer:
        return -1
    return (4 if rule_referrer else 0) + (2 if rule_category else 0) + (1 if rule_segment else 0)


def _in_window(rule: Any, today: date) -> bool:
    if rule.starts_on and today < rule.starts_on:
        return False
    if rule.ends_on and today > rule.ends_on:
        return False
    return True


def pick_rate(
    rules: Iterable[Any],
    *,
    referrer_id: Optional[str],
    category: Optional[str],
    today: date,
    default_type: str,
    default_value: Decimal,
    referrer_is_customer: bool = False,
    existing_customer_type: Optional[str] = None,
    existing_customer_value: Optional[Decimal] = None,
) -> RateChoice:
    best: Optional[tuple[int, datetime, Any]] = None
    for rule in rules:
        if not rule.active or not _in_window(rule, today):
            continue
        score = _specificity(rule, referrer_id, category, referrer_is_customer)
        if score < 0:
            continue
        created = rule.created_at or datetime.min
        if best is None or (score, created) > (best[0], best[1]):
            best = (score, created, rule)
    if best is None:
        if referrer_is_customer and existing_customer_value is not None:
            return RateChoice(
                existing_customer_type or default_type, Decimal(existing_customer_value), None, None, "Existing-customer rate"
            )
        return RateChoice(default_type, Decimal(default_value), None, None, "Default rate")
    rule = best[2]
    return RateChoice(
        rule.rate_type,
        Decimal(rule.rate_value),
        Decimal(rule.max_amount) if rule.max_amount is not None else None,
        str(rule.id),
        rule.name,
    )


def compute_amount(
    choice: RateChoice,
    premium: Decimal,
    *,
    global_cap: Optional[Decimal] = None,
) -> Decimal:
    """Commission for one policy. Percent rates apply to the policy's premium;
    fixed rates are a flat amount per policy. The rule's own cap and then the
    program-wide cap are applied last. Never negative."""
    premium = Decimal(premium)
    if choice.rate_type == "percent":
        amount = premium * choice.rate_value / Decimal("100")
    else:
        amount = choice.rate_value
    if choice.max_amount is not None:
        amount = min(amount, choice.max_amount)
    if global_cap is not None:
        amount = min(amount, Decimal(global_cap))
    return max(amount, Decimal("0")).quantize(CENT, rounding=ROUND_HALF_UP)


def add_months(start: datetime, months: int) -> datetime:
    """`start` plus whole calendar months (day clipped to month end)."""
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    days_in_month = [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return start.replace(year=year, month=month, day=min(start.day, days_in_month[month - 1]))
