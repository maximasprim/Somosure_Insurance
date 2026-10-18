"""One anniversary date for all of a customer's covers - pure Python, no database.

The idea (from the Bidii Credit IPF deck: "renewal of all insurance covers on one
anniversary date"): a customer's policies expire on different days. Pick one common
anniversary; each policy's NEXT renewal is then cut to run only until that date (a
short-period cover), after which every policy renews together each year.

What the insurers will charge for a short period varies, so nothing is hard-coded:
staff set the method and the numbers (see AnniversarySettings / ShortPeriodScale):

  * method "pro_rata_daily": annual premium x days / days-in-a-year;
  * method "short_period_scale": the insurer's own table - "cover up to N days costs
    P% of the annual premium". The first band the term fits in is used; a term longer
    than every band falls back to pro-rata (never silently to a full year);
  * a minimum premium (as a % of the annual premium) that a short period never goes below.

The premium figures are ESTIMATES built from the policy's current premium - the real
renewal premium is whatever the insurer quotes at renewal.

Strategies for the next renewal, given the policy's expiry and the anniversary:
  already_aligned - it expires on the anniversary: a normal full-year renewal;
  short_period    - cover from expiry to the next anniversary;
  long_period     - when that stub would be shorter than `min_stub_days`, run on to the
                    anniversary after it instead - but only if the insurer allows a term
                    that long (`max_term_days`; the default, 366, rules it out).
"""

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Iterable, Sequence

METHODS = ("pro_rata_daily", "short_period_scale")


def money(value: Any) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def occurrence(anniversary: date, year: int) -> date:
    """The anniversary's month/day in `year` (29 Feb becomes 28 Feb in a non-leap year)."""
    try:
        return date(year, anniversary.month, anniversary.day)
    except ValueError:
        return date(year, 2, 28)


def next_occurrence_on_or_after(anniversary: date, day: date) -> date:
    this_year = occurrence(anniversary, day.year)
    return this_year if this_year >= day else occurrence(anniversary, day.year + 1)


def renewal_term(
    *, end_date: date, anniversary: date, min_stub_days: int = 30, max_term_days: int = 366
) -> dict:
    """How a policy ending on `end_date` should next be renewed to land on `anniversary`."""
    start = end_date  # the renewal picks up where the policy ends
    stub_end = next_occurrence_on_or_after(anniversary, end_date)
    if stub_end == end_date:
        new_end = next_occurrence_on_or_after(anniversary, end_date + timedelta(days=1))
        return {
            "strategy": "already_aligned",
            "new_start": start,
            "new_end": new_end,
            "term_days": (new_end - start).days,
            "stub_days": 0,
            "very_short": False,
            "note": "Already expires on the anniversary - renew for a normal full year.",
        }
    stub_days = (stub_end - end_date).days
    if stub_days >= min_stub_days:
        return {
            "strategy": "short_period",
            "new_start": start,
            "new_end": stub_end,
            "term_days": stub_days,
            "stub_days": stub_days,
            "very_short": False,
            "note": f"Renew for {stub_days} days to reach the anniversary, then all covers renew together.",
        }
    long_end = next_occurrence_on_or_after(anniversary, stub_end + timedelta(days=1))
    long_days = (long_end - start).days
    if long_days <= max_term_days:
        return {
            "strategy": "long_period",
            "new_start": start,
            "new_end": long_end,
            "term_days": long_days,
            "stub_days": stub_days,
            "very_short": True,
            "note": f"Only {stub_days} days from the anniversary, so run on to the one after it ({long_days} days).",
        }
    return {
        "strategy": "short_period",
        "new_start": start,
        "new_end": stub_end,
        "term_days": stub_days,
        "stub_days": stub_days,
        "very_short": True,
        "note": (
            f"Only {stub_days} days from the anniversary. A cover that short is rarely worth issuing, and a longer "
            f"term isn't allowed (max {max_term_days} days) - consider aligning at a later renewal."
        ),
    }


def term_premium(
    *,
    annual_premium: Any,
    term_days: int,
    strategy: str,
    method: str,
    scale_rows: Sequence[Any] = (),
    year_basis_days: int = 365,
    minimum_premium_pct: Any = 0,
) -> dict:
    """Estimated premium for the renewal term. `scale_rows` need `.up_to_days` and `.percent_of_annual`."""
    annual = Decimal(str(annual_premium))
    pro_rata = annual * term_days / year_basis_days

    if strategy == "already_aligned":
        return {"premium": money(annual), "method_used": "full_year", "percent_of_annual": Decimal("100.00")}
    if strategy == "long_period":
        premium = pro_rata  # longer than a year: pro-rata, never capped
        return {"premium": money(premium), "method_used": "pro_rata_daily", "percent_of_annual": money(premium / annual * 100) if annual else Decimal("0.00")}

    premium, method_used = pro_rata, "pro_rata_daily"
    if method == "short_period_scale":
        for row in sorted(scale_rows, key=lambda r: r.up_to_days):
            if row.up_to_days >= term_days:
                premium = annual * Decimal(str(row.percent_of_annual)) / 100
                method_used = "short_period_scale"
                break
    floor = annual * Decimal(str(minimum_premium_pct)) / 100
    if premium < floor:
        premium, method_used = floor, f"{method_used}+minimum"
    premium = min(premium, annual)  # a short period never costs more than the full year
    return {
        "premium": money(premium),
        "method_used": method_used,
        "percent_of_annual": money(premium / annual * 100) if annual else Decimal("0.00"),
    }


def suggest_anniversary(end_dates: Iterable[date]) -> date | None:
    """The latest expiry among the customer's covers: every other policy then needs a
    short period to reach it, and the latest one is already aligned."""
    dates = list(end_dates)
    return max(dates) if dates else None
