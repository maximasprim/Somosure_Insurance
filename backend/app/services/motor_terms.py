"""Broker-configurable motor terms: eligibility, payment plans, benefits.

Everything here is PURE - no database, no framework imports - so the rules
can be unit-tested in isolation (tests/test_motor_terms.py) and reused by
the quote engine, the payment service and the admin API alike.

What is configurable per broker (all of it optional):

* Comprehensive eligibility - a minimum sum insured and a maximum vehicle
  age. A vehicle outside either limit is offered Third Party Only (the CIC
  behaviour) or declined outright, per the broker's `ineligible_action`.
* Payment plans - pay in full, or a deposit (e.g. 30%) followed by N monthly
  instalments (e.g. 3 or 4), or straight monthly payments. A plan can also
  say each payment buys one month of sticker cover.
* Included ("free") benefits with limits - windscreen, radio, towing, third
  party property damage, and so on. Display-only: they add no premium.
* Optional extra benefits with a limit and a price - courtesy car, loss of
  keys, political violence, excess protector and so on. These are stored as
  `RateCardExtension` rows, priced by `extension_amount` below.

Money is `Decimal` throughout and serialised to strings when it has to sit
in a JSON column, matching the rest of the pricing code.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from typing import Any

TWO_PLACES = Decimal("0.01")

# Defaults a broker's admin form is pre-filled with. They are NOT applied
# to a broker automatically - a broker with no configured terms prices
# exactly as it always has.
DEFAULT_COMPREHENSIVE_MIN_SUM_INSURED = Decimal("500000")
DEFAULT_COMPREHENSIVE_MAX_VEHICLE_AGE_YEARS = 15

INELIGIBLE_ACTIONS = ("downgrade_to_tpo", "decline")
PLAN_TYPES = ("full", "installments")
COVER_TYPES = ("comprehensive", "tpo")


def to_decimal(value: Any, default: str = "0") -> Decimal:
    if value is None or value == "":
        return Decimal(default)
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001 - anything unparseable falls back
        return Decimal(default)


def money(value: Decimal) -> str:
    """'1,234' style for human-readable reasons (whole shillings)."""
    return f"{int(value.quantize(Decimal('1'), rounding=ROUND_HALF_UP)):,}"


# --------------------------------------------------------------------------
# Eligibility
# --------------------------------------------------------------------------


@dataclass
class Eligibility:
    eligible: bool
    reasons: list[str] = field(default_factory=list)  # why NOT eligible
    unchecked: list[str] = field(default_factory=list)  # what we couldn't verify


def check_comprehensive_eligibility(
    *,
    sum_insured: Decimal | None,
    vehicle_year: Any,
    min_sum_insured: Decimal | None,
    max_vehicle_age_years: int | None,
    today: date | None = None,
) -> Eligibility:
    """A limit set to None is simply not enforced."""
    today = today or date.today()
    reasons: list[str] = []
    unchecked: list[str] = []

    if min_sum_insured is not None:
        value = sum_insured if sum_insured is not None else Decimal("0")
        if value < min_sum_insured:
            reasons.append(
                f"Vehicle value KES {money(value)} is below the KES {money(min_sum_insured)} "
                "minimum for comprehensive cover."
            )

    if max_vehicle_age_years is not None:
        try:
            year = int(str(vehicle_year).strip())
        except (TypeError, ValueError):
            year = None
        if year is None:
            unchecked.append("Vehicle year was not provided, so the vehicle-age limit could not be checked.")
        else:
            age = today.year - year
            if age > max_vehicle_age_years:
                reasons.append(
                    f"The vehicle is {age} years old; comprehensive cover is only offered for vehicles "
                    f"up to {max_vehicle_age_years} years old."
                )

    return Eligibility(eligible=not reasons, reasons=reasons, unchecked=unchecked)


# --------------------------------------------------------------------------
# Extra-benefit pricing (kept identical to the original engine branch)
# --------------------------------------------------------------------------


def extension_amount(
    *,
    basis: str,
    rate_percent: Decimal | None,
    flat_amount: Decimal | None,
    min_amount: Decimal | None,
    sum_insured: Decimal,
    seating_capacity: Any = None,
) -> Decimal:
    if basis == "percent_of_sum_insured":
        amount = sum_insured * ((rate_percent or Decimal("0")) / Decimal("100"))
        return max(amount, min_amount or Decimal("0"))
    if basis == "per_person":
        passengers = to_decimal(seating_capacity, default="1")
        return (flat_amount or Decimal("0")) * passengers
    return flat_amount or Decimal("0")


# --------------------------------------------------------------------------
# Payment plans
# --------------------------------------------------------------------------


def add_months(start: date, months: int) -> date:
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _split(total: Decimal, parts: int) -> list[Decimal]:
    """Splits into `parts` amounts that sum EXACTLY to total; the last one
    absorbs the rounding remainder."""
    each = (total / parts).quantize(TWO_PLACES, rounding=ROUND_DOWN)
    amounts = [each] * parts
    amounts[-1] = total - each * (parts - 1)
    return amounts


def applies_to_cover(plan: dict[str, Any], cover_type: str) -> bool:
    applies = plan.get("applies_to") or list(COVER_TYPES)
    return cover_type in applies


def build_plan_options(
    plan: dict[str, Any], total: Decimal, cover_type: str, start: date | None = None
) -> list[dict[str, Any]]:
    """Every concrete way a customer can take one configured plan, each with
    its full schedule. Returns [] when the plan is disabled or doesn't apply
    to this cover type. All values are JSON-safe (strings for money/dates)."""
    start = start or date.today()
    if not plan.get("enabled", True) or not applies_to_cover(plan, cover_type):
        return []

    base = {"plan_code": plan["code"], "label": plan.get("label") or plan["code"], "type": plan["type"]}
    total = total.quantize(TWO_PLACES)

    if plan["type"] == "full":
        return [
            {
                **base,
                "installments": 0,
                "deposit_percent": "0",
                "due_now": str(total),
                "schedule": [
                    {"sequence": 1, "kind": "full", "due_date": start.isoformat(), "amount": str(total)}
                ],
            }
        ]

    deposit_percent = to_decimal(plan.get("deposit_percent"), "0")
    sticker_months = plan.get("sticker_months_per_payment")
    options: list[dict[str, Any]] = []

    for n in sorted({int(x) for x in (plan.get("installment_options") or [])}):
        if n < 1:
            continue
        if deposit_percent > 0:
            deposit = (total * deposit_percent / Decimal("100")).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
            amounts = [deposit] + _split(total - deposit, n)
            kinds = ["deposit"] + ["installment"] * n
        else:
            amounts = _split(total, n)
            kinds = ["installment"] * n

        schedule = []
        for index, (amount, kind) in enumerate(zip(amounts, kinds)):
            # With a deposit, payment #0 is the deposit and payment #k is due
            # k months later; without one, payment #0 is simply the first
            # monthly payment, due now.
            item: dict[str, Any] = {
                "sequence": index + 1,
                "kind": kind,
                "due_date": add_months(start, index).isoformat(),
                "amount": str(amount),
            }
            if sticker_months:
                cover_from = add_months(start, index * int(sticker_months))
                cover_to = add_months(start, (index + 1) * int(sticker_months)) - timedelta(days=1)
                item["cover_from"] = cover_from.isoformat()
                item["cover_to"] = cover_to.isoformat()
            schedule.append(item)

        options.append(
            {
                **base,
                "installments": n,
                "deposit_percent": str(deposit_percent),
                "due_now": schedule[0]["amount"],
                "sticker_months_per_payment": int(sticker_months) if sticker_months else None,
                "schedule": schedule,
            }
        )
    return options


def build_all_options(
    plans: list[dict[str, Any]] | None, total: Decimal, cover_type: str, start: date | None = None
) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    for plan in plans or []:
        options.extend(build_plan_options(plan, total, cover_type, start))
    return options


def find_option(options: list[dict[str, Any]], plan_code: str, installments: int) -> dict[str, Any] | None:
    for option in options:
        if option["plan_code"] == plan_code and int(option["installments"]) == int(installments):
            return option
    return None


# --------------------------------------------------------------------------
# Catalog + starter template (used to pre-fill the admin form)
# --------------------------------------------------------------------------

# Canonical codes, so "courtesy_car" means the same thing for every broker.
# Existing seeded codes (pvt, excess_protector, courtesy_car, pll) are reused.
FREE_BENEFIT_CATALOG: list[dict[str, Any]] = [
    {"code": "windscreen", "label": "Windscreen"},
    {"code": "entertainment_system", "label": "Vehicle entertainment system (radio)"},
    {"code": "third_party_property_damage", "label": "Third party property damage"},
    {"code": "third_party_bodily_injury", "label": "Third party bodily injury / death"},
    {"code": "passenger_legal_liability", "label": "Third party passenger legal liability"},
    {"code": "emergency_medical", "label": "Emergency medical expenses (vehicle occupants)"},
    {"code": "riot_strike", "label": "Riot and strike"},
    {"code": "towing_recovery", "label": "Towing and recovery"},
    {"code": "authorized_repair_limit", "label": "Authorized repair limit"},
]

EXTRA_BENEFIT_CATALOG: list[dict[str, Any]] = [
    {"code": "courtesy_car", "label": "Loss of use (courtesy car)"},
    {"code": "loss_of_keys", "label": "Loss of keys"},
    {"code": "pvt", "label": "Political violence and terrorism"},
    {"code": "excess_protector", "label": "Excess protector"},
    {"code": "spare_wheel", "label": "Theft / loss of spare wheel"},
    {"code": "accessories_theft", "label": "Theft of accessories (jack, spanners)"},
    {"code": "forced_atm_withdrawal", "label": "Forced ATM withdrawal following a carjacking"},
    {"code": "out_of_station_accommodation", "label": "Out-of-station accommodation after an admissible claim"},
    {"code": "personal_effects", "label": "Personal effects after an admissible claim"},
]


def starter_template() -> dict[str, Any]:
    """A typical broker's motor terms, modelled on CIC's private-motor
    schedule (effective 1 July 2026). It is only a starting point the admin
    can edit - nothing is applied until the admin saves it."""
    return {
        "eligibility": {
            "enabled": True,
            "comprehensive_min_sum_insured": str(DEFAULT_COMPREHENSIVE_MIN_SUM_INSURED),
            "comprehensive_max_vehicle_age_years": DEFAULT_COMPREHENSIVE_MAX_VEHICLE_AGE_YEARS,
            "ineligible_action": "downgrade_to_tpo",
        },
        "payment_plans": [
            {"code": "full", "label": "Pay in full", "type": "full", "enabled": True,
             "applies_to": ["comprehensive", "tpo"]},
            {"code": "deposit_30", "label": "30% deposit, balance in monthly instalments", "type": "installments",
             "enabled": True, "applies_to": ["comprehensive"], "deposit_percent": "30",
             "installment_options": [3, 4], "sticker_months_per_payment": None},
            {"code": "monthly", "label": "Pay monthly (one-month sticker per payment)", "type": "installments",
             "enabled": True, "applies_to": ["comprehensive"], "deposit_percent": "0",
             "installment_options": [12], "sticker_months_per_payment": 1},
        ],
        "free_benefits": [
            {"code": "windscreen", "label": "Windscreen", "limit_amount": "30000",
             "limit_label": "Up to KES 30,000", "top_up_note": "KES 1,000 per additional KES 10,000 cover"},
            {"code": "entertainment_system", "label": "Vehicle entertainment system (radio)",
             "limit_amount": "30000", "limit_label": "Up to KES 30,000",
             "top_up_note": "KES 1,000 per additional KES 10,000 cover"},
            {"code": "third_party_property_damage", "label": "Third party property damage",
             "limit_amount": "5000000", "limit_label": "Up to KES 5,000,000",
             "top_up_note": "KES 1,000 per additional KES 1,000,000 cover"},
            {"code": "third_party_bodily_injury", "label": "Third party bodily injury / death",
             "limit_amount": "3000000", "limit_label": "KES 3,000,000 per person, unlimited per event"},
            {"code": "passenger_legal_liability", "label": "Third party passenger legal liability",
             "limit_amount": "3000000", "limit_label": "KES 3,000,000 per person, KES 20,000,000 per event"},
            {"code": "emergency_medical", "label": "Emergency medical expenses (vehicle occupants)",
             "limit_amount": "30000", "limit_label": "Up to KES 30,000, on reimbursement basis"},
            {"code": "riot_strike", "label": "Riot and strike", "limit_label": "Applicable"},
            {"code": "towing_recovery", "label": "Towing and recovery", "limit_amount": "30000",
             "limit_label": "Up to KES 30,000"},
            {"code": "authorized_repair_limit", "label": "Authorized repair limit", "limit_amount": "50000",
             "limit_label": "Up to KES 50,000"},
        ],
        "extra_benefits": [
            {"code": "courtesy_car", "label": "Loss of use (courtesy car)", "basis": "flat",
             "flat_amount": "3000", "limit_amount": "30000", "limit_label": "Up to KES 30,000, from 3 days after full claim documentation"},
            {"code": "loss_of_keys", "label": "Loss of keys", "basis": "flat", "flat_amount": "2000",
             "limit_amount": "20000", "limit_label": "Up to KES 20,000"},
            {"code": "pvt", "label": "Political violence and terrorism", "basis": "percent_of_sum_insured",
             "rate_percent": "0.25", "min_amount": "2500", "limit_label": "Up to the sum insured"},
            {"code": "excess_protector", "label": "Excess protector (own damage)",
             "basis": "percent_of_sum_insured", "rate_percent": "0.25", "min_amount": "5000",
             "limit_label": "Waives the own-damage excess"},
            {"code": "spare_wheel", "label": "Theft / loss of spare wheel", "basis": "flat",
             "flat_amount": "3000", "limit_amount": "30000", "limit_label": "Up to KES 30,000"},
            {"code": "accessories_theft", "label": "Theft of accessories (jack, spanners)", "basis": "flat",
             "flat_amount": "1500", "limit_amount": "15000", "limit_label": "Up to KES 15,000"},
            {"code": "forced_atm_withdrawal", "label": "Forced ATM withdrawal following a carjacking",
             "basis": "flat", "flat_amount": "4000", "limit_amount": "40000", "limit_label": "Up to KES 40,000"},
            {"code": "out_of_station_accommodation",
             "label": "Out-of-station accommodation after an admissible claim", "basis": "flat",
             "flat_amount": "2000", "limit_amount": "20000",
             "limit_label": "Up to KES 20,000, beyond 50 km from home or workstation"},
            {"code": "personal_effects", "label": "Personal effects after an admissible claim", "basis": "flat",
             "flat_amount": "2000", "limit_amount": "20000", "limit_label": "Up to KES 20,000"},
        ],
    }
