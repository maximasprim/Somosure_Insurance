"""Computes a real premium from a provider's configured rate card (see
app/models/rate_card.py) rather than calling a live insurer API. Used by
RateCardAdapter (app/providers/rate_card_adapter.py) for any provider
whose integration_mode is "rate_card" - currently AMACO and Pioneer
Insurance Kenya, seeded from real published rate cards (see
app/db/rate_card_seed_data.py and docs/RATE_CARDS.md).

Kept independent of the provider adapter interface so it can be unit
tested directly (backend/tests/test_rate_card_engine.py) without going
through the full quote-request flow.
"""

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rate_card import RateCardExcess, RateCardExtension, RateCardTier, RateCardVehicleClass

# Kenyan motor insurance statutory levies (industry-standard, not
# insurer-specific): Policyholders Compensation Fund 0.25% of gross
# premium, IRA Training Levy 0.20% of gross premium, and a flat Kshs. 40
# stamp duty per new policy - the same Kshs. 40 figure AMACO's PSV TPO
# schedule and Pioneer's rate sheet both call out explicitly.
PHCF_RATE = Decimal("0.0025")
TRAINING_LEVY_RATE = Decimal("0.0020")
STAMP_DUTY = Decimal("40.00")

TWO_PLACES = Decimal("0.01")


class RateCardNotConfigured(Exception):
    """Raised when the requested product/vehicle class/cover type has no
    rate card data for this provider yet - a genuine "we don't have that
    priced" rather than a bug. Callers (RateCardAdapter) let this surface
    as a normal per-provider quote failure, exactly like a provider whose
    live API happened to be down (see quote_service.request_quotes)."""


def _to_decimal(value: Any, default: str = "0") -> Decimal:
    if value is None or value == "":
        return Decimal(default)
    return Decimal(str(value))


def resolve_vehicle_class_code(product_category: str, answers: dict[str, Any]) -> str:
    """Maps the quote form's answers to a canonical rate-card class code
    (docs/RATE_CARDS.md has the full list). An explicit `vehicle_class`
    answer always wins - it's what the frontend's class picker sends once
    the customer has narrowed down usage/PSV type - falling back to a
    coarse default from `usage`/`psv_type` for older/simpler callers.
    """
    explicit = answers.get("vehicle_class")
    if explicit:
        return explicit

    if product_category != "motor":
        # Only motor is seeded today; a future medical/life/travel rate
        # card would need its own resolver, not this motor-specific one.
        raise RateCardNotConfigured(
            f"No vehicle_class given and no default class-resolution rule exists for product "
            f"category '{product_category}' yet."
        )

    usage = (answers.get("usage") or "private").lower()
    if usage == "psv":
        psv_type = (answers.get("psv_type") or "taxi_online").lower()
        return {
            "taxi_yellow": "psv_taxi",
            "taxi_chauffeur": "psv_taxi",
            "taxi_online": "psv_taxi",
            "tour_van": "psv_tour_vehicle",
            "matatu": "psv_matatu_bus",
            "bus": "psv_matatu_bus",
            "tuktuk": "psv_tuktuk",
        }.get(psv_type, "psv_taxi")

    if usage == "commercial":
        return "motor_commercial_general_cartage"

    return "motor_private"


def resolve_cover_type(answers: dict[str, Any]) -> str:
    cover_type = (answers.get("cover_type") or "comprehensive").lower()
    return "comprehensive" if cover_type == "comprehensive" else "tpo"


def _select_tier(tiers: list[RateCardTier], answers: dict[str, Any]) -> tuple[RateCardTier, list[str]]:
    """Picks the one tier that matches the request's band value. Returns
    the tier plus a list of human-readable assumption notes (e.g. "no
    tonnage given, used lightest band") so the caller can surface them in
    the quote's coverage/metadata rather than silently guessing.
    """
    notes: list[str] = []
    band_unit = tiers[0].band_unit

    if band_unit == "none":
        return tiers[0], notes

    if band_unit == "subtype":
        subtype = answers.get("vehicle_subtype")
        for tier in tiers:
            if tier.subtype_key == subtype:
                return tier, notes
        default_tier = tiers[0]
        notes.append(
            f"No vehicle_subtype given (or '{subtype}' not recognised for this class); "
            f"defaulted to '{default_tier.subtype_key}'. Provide vehicle_subtype for an exact quote."
        )
        return default_tier, notes

    field_by_unit = {"sum_insured": "value", "tonnes": "tonnage", "passengers": "seating_capacity"}
    field_name = field_by_unit.get(band_unit)
    raw_value = answers.get(field_name)
    if raw_value in (None, ""):
        notes.append(f"No '{field_name}' given for a {band_unit}-banded class; used the lowest configured band.")
        value = tiers[0].min_value or Decimal("0")
    else:
        value = _to_decimal(raw_value)

    for tier in sorted(tiers, key=lambda t: (t.min_value if t.min_value is not None else Decimal("-1"))):
        lo = tier.min_value if tier.min_value is not None else Decimal("-Infinity")
        hi = tier.max_value if tier.max_value is not None else Decimal("Infinity")
        if lo <= value <= hi:
            return tier, notes

    # Value falls outside every configured band (e.g. below the lowest
    # minimum) - use the nearest band rather than failing the whole quote,
    # but say so plainly.
    nearest = min(tiers, key=lambda t: abs((t.min_value or Decimal("0")) - value))
    notes.append(
        f"{field_name}={value} falls outside every configured {band_unit} band for this class; "
        f"used the nearest configured band ('{nearest.label or nearest.id}'). Add a wider band via the admin API."
    )
    return nearest, notes


def _tier_amount(tier: RateCardTier, sum_insured: Decimal) -> Decimal:
    if tier.rate_percent is not None:
        amount = sum_insured * (tier.rate_percent / Decimal("100"))
    else:
        amount = tier.flat_amount or Decimal("0")
    if tier.min_premium is not None:
        amount = max(amount, tier.min_premium)
    return amount


@dataclass
class RateCardQuoteBreakdown:
    vehicle_class_label: str
    cover_type: str
    base_premium: Decimal
    extensions: list[dict[str, Any]] = field(default_factory=list)
    extensions_total: Decimal = Decimal("0")
    phcf: Decimal = Decimal("0")
    training_levy: Decimal = Decimal("0")
    stamp_duty: Decimal = Decimal("0")
    total: Decimal = Decimal("0")
    excesses: list[dict[str, Any]] = field(default_factory=list)
    data_confidence: str = "verified"
    source_document: str | None = None
    assumptions: list[str] = field(default_factory=list)


async def compute_motor_premium(
    db: AsyncSession, provider_id: str, answers: dict[str, Any]
) -> RateCardQuoteBreakdown:
    class_code = resolve_vehicle_class_code("motor", answers)
    cover_type = resolve_cover_type(answers)

    vehicle_class = await db.scalar(
        select(RateCardVehicleClass).where(
            RateCardVehicleClass.provider_id == provider_id,
            RateCardVehicleClass.code == class_code,
            RateCardVehicleClass.is_active.is_(True),
        )
    )
    if not vehicle_class:
        raise RateCardNotConfigured(f"No active '{class_code}' vehicle class configured for this provider.")

    tiers = (
        await db.scalars(
            select(RateCardTier)
            .where(RateCardTier.vehicle_class_id == vehicle_class.id, RateCardTier.cover_type == cover_type)
            .order_by(RateCardTier.tier_order)
        )
    ).all()
    if not tiers:
        raise RateCardNotConfigured(
            f"'{vehicle_class.label}' has no {cover_type} rates configured for this provider yet."
        )

    tier, assumptions = _select_tier(list(tiers), answers)
    sum_insured = _to_decimal(answers.get("value"))
    base_premium = _tier_amount(tier, sum_insured)

    if answers.get("cover_type") == "third_party_fire_theft" and cover_type == "tpo":
        assumptions.append(
            "Third Party, Fire & Theft priced as Third Party Only - the source rate card has no separate "
            "fire-and-theft loading for this class."
        )

    extensions_breakdown: list[dict[str, Any]] = []
    extensions_total = Decimal("0")
    requested_extensions = answers.get("extensions") or []
    if requested_extensions:
        rows = (
            await db.scalars(
                select(RateCardExtension).where(
                    RateCardExtension.provider_id == provider_id,
                    RateCardExtension.code.in_(requested_extensions),
                )
            )
        ).all()
        # Prefer a class-specific override over the provider-wide default
        # for the same code.
        by_code: dict[str, RateCardExtension] = {}
        for row in rows:
            if row.vehicle_class_id == vehicle_class.id or row.vehicle_class_id is None:
                if row.code not in by_code or row.vehicle_class_id == vehicle_class.id:
                    by_code[row.code] = row

        for code in requested_extensions:
            ext = by_code.get(code)
            if not ext:
                assumptions.append(f"Requested extension '{code}' is not configured for this provider - skipped.")
                continue
            if ext.basis == "percent_of_sum_insured":
                amount = sum_insured * ((ext.rate_percent or Decimal("0")) / Decimal("100"))
                amount = max(amount, ext.min_amount or Decimal("0"))
            elif ext.basis == "per_person":
                passengers = _to_decimal(answers.get("seating_capacity"), default="1")
                amount = (ext.flat_amount or Decimal("0")) * passengers
            else:
                amount = ext.flat_amount or Decimal("0")
            extensions_total += amount
            extensions_breakdown.append({"code": ext.code, "label": ext.label, "amount": str(amount.quantize(TWO_PLACES))})

    subtotal = base_premium + extensions_total
    phcf = (subtotal * PHCF_RATE).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    training_levy = (subtotal * TRAINING_LEVY_RATE).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    total = (subtotal + phcf + training_levy + STAMP_DUTY).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    excess_rows = (
        await db.scalars(select(RateCardExcess).where(RateCardExcess.vehicle_class_id == vehicle_class.id))
    ).all()
    excesses = [
        {
            "peril": row.peril,
            "label": row.label
            or (f"{row.rate_percent}% of sum insured, min Kshs. {row.min_amount}" if row.rate_percent else str(row.flat_amount)),
        }
        for row in excess_rows
    ]

    return RateCardQuoteBreakdown(
        vehicle_class_label=vehicle_class.label,
        cover_type=cover_type,
        base_premium=base_premium.quantize(TWO_PLACES),
        extensions=extensions_breakdown,
        extensions_total=extensions_total.quantize(TWO_PLACES),
        phcf=phcf,
        training_levy=training_levy,
        stamp_duty=STAMP_DUTY,
        total=total,
        excesses=excesses,
        data_confidence=vehicle_class.data_confidence,
        source_document=vehicle_class.source_document,
        assumptions=assumptions,
    )
