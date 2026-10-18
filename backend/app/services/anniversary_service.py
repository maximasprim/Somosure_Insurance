"""Renewing all of a customer's covers on one anniversary date.

Reads policies and writes only to the new tables (models/pricing_config.py). It never
issues, changes or renews a policy - it works out what a renewal aligned to the
customer's anniversary would look like (the term, and an ESTIMATED short-period
premium using the rules staff configure) and shows it. The arithmetic is in
anniversary_math.py.
"""

import logging
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.policy import Policy
from app.models.pricing_config import (
    ANNIVERSARY_SETTINGS_ID,
    AnniversarySettings,
    CustomerAnniversary,
    ShortPeriodScale,
)
from app.models.provider import InsuranceProvider
from app.services import anniversary_math

logger = logging.getLogger("somosure.anniversary")


# --- settings -------------------------------------------------------------------------------


async def get_settings(db: AsyncSession) -> AnniversarySettings:
    """The one row of configuration. Created with defaults on first read."""
    settings = await db.get(AnniversarySettings, ANNIVERSARY_SETTINGS_ID)
    if not settings:
        settings = AnniversarySettings(id=ANNIVERSARY_SETTINGS_ID)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    return settings


async def update_settings(db: AsyncSession, payload: Any, actor: Any) -> AnniversarySettings:
    settings = await get_settings(db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is None:  # none of these can be cleared, only changed
            continue
        setattr(settings, field, value)
    settings.updated_by = str(actor) if actor else None
    await db.commit()
    await db.refresh(settings)
    return settings


# --- short-period tables ------------------------------------------------------------------------


async def providers_lite(db: AsyncSession) -> list[InsuranceProvider]:
    return list((await db.scalars(select(InsuranceProvider).order_by(InsuranceProvider.name))).all())


async def list_scales(db: AsyncSession) -> list[dict]:
    names = {p.id: p.name for p in await providers_lite(db)}
    rows = (
        await db.scalars(select(ShortPeriodScale).order_by(ShortPeriodScale.provider_id.nulls_first(), ShortPeriodScale.up_to_days))
    ).all()
    return [
        {
            "id": r.id,
            "provider_id": r.provider_id,
            "provider_name": names.get(r.provider_id) if r.provider_id else None,
            "up_to_days": r.up_to_days,
            "percent_of_annual": r.percent_of_annual,
        }
        for r in rows
    ]


async def _scale_view(db: AsyncSession, scale_id: Any) -> dict:
    for row in await list_scales(db):
        if str(row["id"]) == str(scale_id):
            return row
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Scale band not found")


async def create_scale(db: AsyncSession, payload: Any) -> dict:
    if payload.provider_id is not None and not await db.get(InsuranceProvider, payload.provider_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Provider not found")
    clash = await db.scalar(
        select(ShortPeriodScale.id).where(
            ShortPeriodScale.up_to_days == payload.up_to_days,
            ShortPeriodScale.provider_id.is_(None) if payload.provider_id is None else ShortPeriodScale.provider_id == payload.provider_id,
        )
    )
    if clash:
        raise HTTPException(status.HTTP_409_CONFLICT, f"There is already a band for up to {payload.up_to_days} days in this table")
    row = ShortPeriodScale(provider_id=payload.provider_id, up_to_days=payload.up_to_days, percent_of_annual=payload.percent_of_annual)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return await _scale_view(db, row.id)


async def update_scale(db: AsyncSession, scale_id: Any, payload: Any) -> dict:
    row = await db.get(ShortPeriodScale, scale_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scale band not found")
    changes = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    new_days = changes.get("up_to_days", row.up_to_days)
    if new_days != row.up_to_days:
        clash = await db.scalar(
            select(ShortPeriodScale.id).where(
                ShortPeriodScale.id != row.id,
                ShortPeriodScale.up_to_days == new_days,
                ShortPeriodScale.provider_id.is_(None) if row.provider_id is None else ShortPeriodScale.provider_id == row.provider_id,
            )
        )
        if clash:
            raise HTTPException(status.HTTP_409_CONFLICT, f"There is already a band for up to {new_days} days in this table")
    for field, value in changes.items():
        setattr(row, field, value)
    await db.commit()
    return await _scale_view(db, row.id)


async def delete_scale(db: AsyncSession, scale_id: Any) -> None:
    row = await db.get(ShortPeriodScale, scale_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scale band not found")
    await db.delete(row)
    await db.commit()


async def _scales_by_provider(db: AsyncSession) -> dict[Any, list[ShortPeriodScale]]:
    grouped: dict[Any, list[ShortPeriodScale]] = defaultdict(list)
    for row in (await db.scalars(select(ShortPeriodScale))).all():
        grouped[row.provider_id].append(row)
    return grouped


def _rows_for(grouped: dict[Any, list[ShortPeriodScale]], provider_id: Any) -> list[ShortPeriodScale]:
    """The provider's own table if it has one, else the default table, else none."""
    return grouped.get(provider_id) or grouped.get(None) or []


# --- previewing the numbers -------------------------------------------------------------------------


async def preview_premium(db: AsyncSession, annual_premium: Decimal, term_days: int, provider_id: Any) -> dict:
    """What the configured rules would charge for a cover of `term_days`. A test tool for staff."""
    settings = await get_settings(db)
    rows = _rows_for(await _scales_by_provider(db), provider_id)
    year = settings.year_basis_days
    strategy = "short_period" if term_days < year else ("already_aligned" if term_days <= year + 1 else "long_period")
    result = anniversary_math.term_premium(
        annual_premium=annual_premium,
        term_days=term_days,
        strategy=strategy,
        method=settings.method,
        scale_rows=rows,
        year_basis_days=year,
        minimum_premium_pct=settings.minimum_premium_pct,
    )
    return {"term_days": term_days, **result}


# --- one customer's alignment ------------------------------------------------------------------------


def _align_policy(policy: Policy, provider_name: str | None, anniversary: date, settings: AnniversarySettings, rows: list) -> dict:
    term = anniversary_math.renewal_term(
        end_date=policy.end_date,
        anniversary=anniversary,
        min_stub_days=settings.min_stub_days,
        max_term_days=settings.max_term_days,
    )
    premium = anniversary_math.term_premium(
        annual_premium=policy.premium,
        term_days=term["term_days"],
        strategy=term["strategy"],
        method=settings.method,
        scale_rows=rows,
        year_basis_days=settings.year_basis_days,
        minimum_premium_pct=settings.minimum_premium_pct,
    )
    return {
        "policy_id": policy.id,
        "policy_number": policy.policy_number,
        "provider_name": provider_name,
        "end_date": policy.end_date,
        "annual_premium": anniversary_math.money(policy.premium),
        "strategy": term["strategy"],
        "new_start": term["new_start"],
        "new_end": term["new_end"],
        "term_days": term["term_days"],
        "stub_days": term["stub_days"],
        "very_short": term["very_short"],
        "note": term["note"],
        "estimated_premium": premium["premium"],
        "method_used": premium["method_used"],
        "percent_of_annual": premium["percent_of_annual"],
    }


async def _active_policies(db: AsyncSession, customer_id: Any) -> list[tuple[Policy, str | None]]:
    rows = (
        await db.execute(
            select(Policy, InsuranceProvider.name)
            .outerjoin(InsuranceProvider, InsuranceProvider.id == Policy.provider_id)
            .where(Policy.customer_id == customer_id, Policy.status == "active", Policy.end_date >= date.today())
            .order_by(Policy.end_date)
        )
    ).all()
    return [(p, name) for p, name in rows]


async def customer_plan(db: AsyncSession, customer_id: Any, preview_date: date | None = None) -> dict:
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")
    settings = await get_settings(db)
    saved = await db.scalar(select(CustomerAnniversary).where(CustomerAnniversary.customer_id == customer.id))
    policies = await _active_policies(db, customer.id)
    suggested = anniversary_math.suggest_anniversary(p.end_date for p, _ in policies)

    anniversary = saved.anniversary_date if saved else (preview_date or suggested)
    grouped = await _scales_by_provider(db)
    plan = (
        [_align_policy(p, name, anniversary, settings, _rows_for(grouped, p.provider_id)) for p, name in policies]
        if anniversary
        else []
    )
    return {
        "customer_id": customer.id,
        "customer_name": customer.full_name,
        "enabled": settings.enabled,
        "anniversary_date": saved.anniversary_date if saved else None,
        "notes": saved.notes if saved else None,
        "suggested_anniversary": suggested,
        "using_suggestion": saved is None and anniversary is not None,
        "policies": plan,
    }


async def set_customer_anniversary(db: AsyncSession, customer_id: Any, anniversary_date: date, notes: str | None, actor: Any) -> None:
    if not await db.get(Customer, customer_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")
    row = await db.scalar(select(CustomerAnniversary).where(CustomerAnniversary.customer_id == customer_id))
    if row:
        row.anniversary_date, row.notes, row.set_by = anniversary_date, notes, (str(actor) if actor else None)
    else:
        db.add(CustomerAnniversary(customer_id=customer_id, anniversary_date=anniversary_date, notes=notes, set_by=str(actor) if actor else None))
    await db.commit()


async def clear_customer_anniversary(db: AsyncSession, customer_id: Any) -> None:
    row = await db.scalar(select(CustomerAnniversary).where(CustomerAnniversary.customer_id == customer_id))
    if row:
        await db.delete(row)
        await db.commit()


async def lookup_customers(db: AsyncSession, search: str) -> list[dict]:
    term = f"%{search.strip()}%"
    customers = (
        await db.scalars(
            select(Customer).where(or_(Customer.full_name.ilike(term), Customer.phone.ilike(term))).order_by(Customer.full_name).limit(15)
        )
    ).all()
    if not customers:
        return []
    ids = [c.id for c in customers]
    counts = dict(
        (
            await db.execute(
                select(Policy.customer_id, func.count(Policy.id))
                .where(Policy.customer_id.in_(ids), Policy.status == "active", Policy.end_date >= date.today())
                .group_by(Policy.customer_id)
            )
        ).all()
    )
    saved = {a.customer_id: a.anniversary_date for a in (await db.scalars(select(CustomerAnniversary).where(CustomerAnniversary.customer_id.in_(ids)))).all()}
    return [
        {"id": c.id, "full_name": c.full_name, "phone": c.phone, "active_policies": int(counts.get(c.id, 0)), "anniversary_date": saved.get(c.id)}
        for c in customers
    ]


async def list_anniversaries(db: AsyncSession) -> list[dict]:
    rows = (
        await db.execute(
            select(CustomerAnniversary, Customer.full_name)
            .join(Customer, Customer.id == CustomerAnniversary.customer_id)
            .order_by(Customer.full_name)
            .limit(300)
        )
    ).all()
    if not rows:
        return []
    ids = [a.customer_id for a, _ in rows]
    counts = dict(
        (
            await db.execute(
                select(Policy.customer_id, func.count(Policy.id))
                .where(Policy.customer_id.in_(ids), Policy.status == "active", Policy.end_date >= date.today())
                .group_by(Policy.customer_id)
            )
        ).all()
    )
    return [
        {"customer_id": a.customer_id, "customer_name": name, "anniversary_date": a.anniversary_date, "active_policies": int(counts.get(a.customer_id, 0))}
        for a, name in rows
    ]


# --- the renewals screen -----------------------------------------------------------------------------


async def _settings_readonly(db: AsyncSession) -> AnniversarySettings:
    """The settings for a read-only screen: the saved row, or defaults that are NOT saved."""
    return await db.get(AnniversarySettings, ANNIVERSARY_SETTINGS_ID) or AnniversarySettings(
        id=ANNIVERSARY_SETTINGS_ID,
        enabled=True,
        method="pro_rata_daily",
        year_basis_days=365,
        minimum_premium_pct=Decimal("0"),
        min_stub_days=30,
        max_term_days=366,
    )


async def renewal_alignments(db: AsyncSession, renewals: list[Any]) -> dict[Any, dict]:
    """For each renewal whose customer has a common anniversary: the aligned term and
    the estimated short-period premium. Keyed by renewal id. Returns {} if the feature
    is switched off or nobody has an anniversary."""
    if not renewals:
        return {}
    settings = await _settings_readonly(db)
    if not settings.enabled:
        return {}
    policy_ids = [r.policy_id for r in renewals]
    policies = {p.id: p for p in (await db.scalars(select(Policy).where(Policy.id.in_(policy_ids)))).all()}
    customer_ids = {p.customer_id for p in policies.values()}
    if not customer_ids:
        return {}
    saved = {
        a.customer_id: a.anniversary_date
        for a in (await db.scalars(select(CustomerAnniversary).where(CustomerAnniversary.customer_id.in_(customer_ids)))).all()
    }
    if not saved:
        return {}
    grouped = await _scales_by_provider(db)

    out: dict[Any, dict] = {}
    for renewal in renewals:
        policy = policies.get(renewal.policy_id)
        anniversary = saved.get(policy.customer_id) if policy else None
        if not policy or anniversary is None:
            continue
        # The renewal's own due date, in case the policy's end date has been edited since.
        view = _align_policy(
            SimpleNamespaceLike(policy, renewal.due_date), None, anniversary, settings, _rows_for(grouped, policy.provider_id)
        )
        out[renewal.id] = {
            "anniversary_date": anniversary,
            "strategy": view["strategy"],
            "new_end": view["new_end"],
            "term_days": view["term_days"],
            "estimated_premium": view["estimated_premium"],
            "very_short": view["very_short"],
            "note": view["note"],
        }
    return out


class SimpleNamespaceLike:
    """A policy as far as alignment is concerned, but ending on the renewal's due date."""

    def __init__(self, policy: Policy, end_date: date):
        self.id = policy.id
        self.policy_number = policy.policy_number
        self.premium = policy.premium
        self.end_date = end_date
