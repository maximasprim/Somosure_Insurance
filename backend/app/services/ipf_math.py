"""The arithmetic behind the IPF extras (early settlement, cheques, loan officer
commission and targets). Pure Python - no database, no web framework - so every rule
can be tested in milliseconds and read in one place. ipf_service.py does the I/O.

Rules, as the Bidii Credit IPF deck describes them:

  * Early settlement: "if a client clears their loan before the agreed term, a waiver
    fee of 3.5% applies". Read here as: the client pays the PRINCIPAL still outstanding
    plus the fee (a % of that principal); the interest and fees still to come in the
    remaining instalments are waived. The fee % is a setting. The total is never more
    than the remaining instalments would have cost.
  * Post-dated cheques: "cheques to cover repayments depending on the number of months"
    - one per monthly instalment - for stand-alone ("unlinked") IPF. A "linked" IPF
    (the client also has an auto loan) is secured by a vehicle tracker instead.
  * Loan officers earn a share (default 10%) of Somosure's NET commission on the policy.
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Sequence

ZERO = Decimal("0.00")


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def settlement_figures(
    *, financed_amount: Decimal, term_months: int, unpaid_instalments: Sequence[Decimal], fee_pct: Decimal
) -> dict:
    """What it costs to clear a loan now. `unpaid_instalments` are the amounts of the
    instalments not yet paid (pending or overdue)."""
    remaining = len(unpaid_instalments)
    would_have_paid = money(sum((Decimal(str(a)) for a in unpaid_instalments), Decimal("0")))
    if remaining == 0 or term_months <= 0:
        return {
            "instalments_remaining": 0,
            "outstanding_principal": ZERO,
            "fee_pct": money(fee_pct),
            "fee_amount": ZERO,
            "total_due": ZERO,
            "would_have_paid": ZERO,
            "saving": ZERO,
            "capped": False,
        }
    # Each instalment carries an equal slice of the principal (interest is flat), so the
    # principal still owed is that slice times the instalments left.
    outstanding_principal = money(Decimal(str(financed_amount)) * remaining / term_months)
    fee = money(outstanding_principal * Decimal(str(fee_pct)) / 100)
    total = outstanding_principal + fee
    capped = False
    if total > would_have_paid:  # never ask for more than simply paying on schedule would
        total = would_have_paid
        fee = max(ZERO, total - outstanding_principal)
        capped = True
    return {
        "instalments_remaining": remaining,
        "outstanding_principal": outstanding_principal,
        "fee_pct": money(fee_pct),
        "fee_amount": fee,
        "total_due": total,
        "would_have_paid": would_have_paid,
        "saving": money(would_have_paid - total),
        "capped": capped,
    }


def cheques_required(ipf_type: str, term_months: int) -> int:
    """Unlinked (stand-alone) IPF: one post-dated cheque per monthly repayment.
    Linked IPF is secured by the vehicle tracker instead."""
    return max(0, int(term_months)) if ipf_type != "linked" else 0


def tracker_required(ipf_type: str) -> bool:
    return ipf_type == "linked"


def commission_basis(*, policy_commission, premium, pct_of_premium) -> Decimal | None:
    """Somosure's net commission on a policy, if it can be known: the figure recorded on
    the policy, else the configured % of premium, else None (finance enters it)."""
    if policy_commission is not None and Decimal(str(policy_commission)) > 0:
        return money(policy_commission)
    if pct_of_premium is not None and Decimal(str(pct_of_premium)) > 0 and premium is not None:
        return money(Decimal(str(premium)) * Decimal(str(pct_of_premium)) / 100)
    return None


def officer_commission(net_commission, rate_pct) -> Decimal:
    return money(Decimal(str(net_commission)) * Decimal(str(rate_pct)) / 100)


def month_window(today: date) -> tuple[date, date]:
    """First day of this month and of the next - the half-open window a monthly target covers."""
    start = today.replace(day=1)
    nxt = date(start.year + (start.month // 12), (start.month % 12) + 1, 1)
    return start, nxt


def target_progress(achieved, target) -> float | None:
    """% of a monthly target reached; None when no target is set."""
    if target is None or Decimal(str(target)) <= 0:
        return None
    return round(float(Decimal(str(achieved)) / Decimal(str(target)) * 100), 1)
