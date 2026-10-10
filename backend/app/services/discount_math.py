"""Pure maths for referral discount credits (no database, no framework).

A referral discount credit is a promise of cheaper insurance for an existing
customer who referred someone who then bought a policy. It is either a
percentage of a policy's premium (before taxes and fees) or a fixed KES amount,
with an optional ceiling. Staff apply it to one of that customer's applications;
the amount is then taken off what they pay.
"""

from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Optional

CENT = Decimal("0.01")


def compute_discount(
    discount_type: str,
    value: Decimal,
    max_amount: Optional[Decimal],
    premium: Decimal,
    total: Decimal,
) -> Decimal:
    """The most this credit can take off an application priced at `premium`
    (net premium) and `total` (what the customer pays). A percentage applies to
    the premium; a fixed amount is flat. Never more than the premium (taxes and
    fees are still payable) and never negative."""
    premium, total = Decimal(premium), Decimal(total)
    amount = premium * Decimal(value) / Decimal("100") if discount_type == "percent" else Decimal(value)
    if max_amount is not None:
        amount = min(amount, Decimal(max_amount))
    amount = min(amount, premium, total)
    return max(amount, Decimal("0")).quantize(CENT, rounding=ROUND_HALF_UP)


MIN_FIRST_PAYMENT = Decimal("1.00")  # M-Pesa can't collect nothing


def apply_discount_to_schedule(schedule: list[dict[str, Any]], discount: Decimal) -> tuple[list[dict[str, Any]], Decimal]:
    """Takes `discount` off the FIRST payment of a payment plan, so the customer
    benefits straight away, and returns (new schedule, amount actually taken).
    The first payment never drops below KES 1, so a large discount on a plan
    with a small deposit is trimmed rather than producing an empty payment.
    The input is untouched; every other leg and field is kept as it was."""
    if not schedule:
        return [], Decimal("0.00")
    legs = [dict(leg) for leg in schedule]
    first = Decimal(str(legs[0]["amount"]))
    take = min(Decimal(discount), max(first - MIN_FIRST_PAYMENT, Decimal("0")))
    take = max(take, Decimal("0")).quantize(CENT, rounding=ROUND_HALF_UP)
    legs[0]["amount"] = str((first - take).quantize(CENT, rounding=ROUND_HALF_UP))
    return legs, take
