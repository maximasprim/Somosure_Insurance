"""Staff-defined pricing tiers for Bidii Credit IPF: the monthly interest rate by loan
amount and term. The matching rules are in rate_tier_math.py.

With no tiers defined, financing is priced exactly as it always was. The lookup used
by the eligibility check is deliberately forgiving: if the tiers table can't be read
(for example a migration hasn't been run yet) it logs the problem and prices at the
standard rate instead of stopping customers applying.
"""

import logging
import uuid
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pricing_config import FinancingRateTier
from app.services import rate_tier_math

logger = logging.getLogger("somosure.pricing")


async def list_tiers(db: AsyncSession) -> list[FinancingRateTier]:
    return list(
        (
            await db.scalars(
                select(FinancingRateTier).order_by(
                    FinancingRateTier.applies_to, FinancingRateTier.min_amount, FinancingRateTier.min_term_months
                )
            )
        ).all()
    )


async def find_rate_tier(db: AsyncSession, financed_amount: Any, term_months: int, is_corporate: bool) -> FinancingRateTier | None:
    try:
        async with db.begin_nested():  # a failure here must not poison the caller's transaction
            tiers = list((await db.scalars(select(FinancingRateTier).where(FinancingRateTier.is_active.is_(True)))).all())
    except Exception:
        logger.exception("Could not read the financing rate tiers - using the standard rate")
        return None
    return rate_tier_math.find_tier(tiers, financed_amount, term_months, is_corporate)


def _validated(values: dict) -> None:
    max_amount = values.get("max_amount")
    if max_amount is not None and Decimal(str(max_amount)) <= Decimal(str(values["min_amount"])):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The upper loan amount must be higher than the lower one")
    max_term = values.get("max_term_months")
    if max_term is not None and max_term < values["min_term_months"]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The longest term can't be shorter than the shortest term")


async def _refuse_overlap(db: AsyncSession, values: dict, ignore_id: Any = None) -> None:
    candidate = SimpleNamespace(**values)
    for other in await list_tiers(db):
        if ignore_id is not None and str(other.id) == str(ignore_id):
            continue
        if rate_tier_math.overlaps(candidate, other):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"This overlaps the tier '{other.label}' ({rate_tier_math.describe(other)}) for the same kind of applicant. "
                "Adjust the ranges, or switch one of them off, so a loan only ever matches one tier.",
            )


def _values(tier: FinancingRateTier | None, changes: dict) -> dict:
    base = {
        "label": None, "applies_to": "all", "min_amount": Decimal("0"), "max_amount": None,
        "min_term_months": 1, "max_term_months": None, "interest_rate_monthly": None, "is_active": True,
    }
    if tier is not None:
        base = {k: getattr(tier, k) for k in base}
    base.update(changes)
    return base


async def create_tier(db: AsyncSession, payload: Any) -> FinancingRateTier:
    values = _values(None, payload.model_dump())
    _validated(values)
    if values["is_active"]:
        await _refuse_overlap(db, values)
    tier = FinancingRateTier(**values)
    db.add(tier)
    await db.commit()
    await db.refresh(tier)
    return tier


async def update_tier(db: AsyncSession, tier_id: Any, payload: Any) -> FinancingRateTier:
    tier = await db.get(FinancingRateTier, tier_id)
    if not tier:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rate tier not found")
    changes = payload.model_dump(exclude_unset=True)
    # A tier always has a label, kind, lower limits, rate and on/off state - those can be changed, never blanked.
    for required in ("label", "applies_to", "min_amount", "min_term_months", "interest_rate_monthly", "is_active"):
        if required in changes and changes[required] is None:
            changes.pop(required)
    values = _values(tier, changes)
    _validated(values)
    if values["is_active"]:
        await _refuse_overlap(db, values, ignore_id=tier.id)
    for field, value in changes.items():
        setattr(tier, field, value)
    await db.commit()
    await db.refresh(tier)
    return tier


async def delete_tier(db: AsyncSession, tier_id: Any) -> None:
    tier = await db.get(FinancingRateTier, tier_id)
    if not tier:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rate tier not found")
    await db.delete(tier)
    await db.commit()


async def preview_rate(db: AsyncSession, amount: Decimal, term_months: int, is_corporate: bool) -> dict:
    """The rate a (non-concession) loan of this size and term gets, and why."""
    from app.services.financing_service import get_financing_settings  # avoids a circular import

    settings = await get_financing_settings(db)
    tier = await find_rate_tier(db, amount, term_months, is_corporate)
    standard = settings.interest_rate_standard_monthly
    if tier is not None:
        return {"rate": tier.interest_rate_monthly, "source": "tier", "tier": tier, "standard_rate": standard}
    if is_corporate and settings.corporate_interest_rate_monthly is not None:
        return {"rate": settings.corporate_interest_rate_monthly, "source": "corporate", "tier": None, "standard_rate": standard}
    return {"rate": standard, "source": "standard", "tier": None, "standard_rate": standard}
