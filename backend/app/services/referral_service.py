import random
import string

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.affiliate import Affiliate
from app.models.customer import Customer
from app.models.policy import Policy
from app.models.referral import Referral


def generate_referral_code() -> str:
    return "SOM" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


async def get_or_create_referral_code(db: AsyncSession, customer_id: str) -> Referral:
    existing = await db.scalar(
        select(Referral).where(Referral.referrer_customer_id == customer_id, Referral.referred_customer_id.is_(None))
    )
    if existing:
        return existing

    code = generate_referral_code()
    referral = Referral(code=code, referrer_customer_id=customer_id, status="pending")
    db.add(referral)
    await db.commit()
    await db.refresh(referral)
    return referral


async def attribute_referrer(
    db: AsyncSession, code: str | None, customer_id: str, *, raise_on_self: bool = True
) -> Referral | None:
    """Links a customer to whoever referred them, using either kind of code:
    an ordinary single-use referral code, or an enrolled affiliate's reusable
    code. Used at registration AND when a guest asks for a quote (most
    customers never register), so referrers get credit either way.

    A customer can only ever be attributed once, and only before they have
    bought anything - referral is for NEW customers. Returns the Referral, or
    None when there is nothing to link (unknown code, already referred, an
    existing customer...). Never marks anything converted: conversion means a
    policy is issued (see mark_converted_if_referred)."""
    code = (code or "").strip().upper()
    if not code:
        return None
    customer_id = str(customer_id)

    if await db.scalar(select(Referral.id).where(Referral.referred_customer_id == customer_id).limit(1)):
        return None
    if await db.scalar(select(Policy.id).where(Policy.customer_id == customer_id).limit(1)):
        return None

    now = datetime.now(timezone.utc)

    referral = await db.scalar(
        select(Referral).where(Referral.code == code, Referral.status == "pending", Referral.referred_customer_id.is_(None))
    )
    if referral:
        if str(referral.referrer_customer_id) == customer_id:
            if raise_on_self:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot refer yourself")
            return None
        referral.referred_customer_id = customer_id
        referral.referred_at = now
        await db.commit()
        await db.refresh(referral)
        return referral

    affiliate = await db.scalar(select(Affiliate).where(Affiliate.code == code, Affiliate.status == "active"))
    if affiliate:
        if str(affiliate.customer_id) == customer_id:
            if raise_on_self:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot refer yourself")
            return None
        row_code = generate_referral_code()
        while await db.scalar(select(Referral.id).where(Referral.code == row_code)):
            row_code = generate_referral_code()
        referral = Referral(
            code=row_code,
            referrer_customer_id=affiliate.customer_id,
            referred_customer_id=customer_id,
            referred_at=now,
            status="pending",
        )
        db.add(referral)
        await db.commit()
        await db.refresh(referral)
        return referral
    return None


async def redeem_referral_code(db: AsyncSession, code: str, new_customer_id: str) -> Referral | None:
    """Links a new customer to the referral that brought them in (see
    attribute_referrer). Doesn't mark it 'converted' yet - conversion means the
    referred customer's first policy issues (mark_converted_if_referred, called
    from policy_service.issue_policy), not just registering."""
    return await attribute_referrer(db, code, new_customer_id, raise_on_self=True)


async def mark_converted_if_referred(db: AsyncSession, customer_id: str, policy_id: str) -> None:
    """Called when a policy is issued - if this customer arrived via a
    referral and this is their first policy, mark the referral converted.
    Reward payment itself is a manual admin action (spec §42: 'keep reward
    logic configurable'), not automated here."""
    referral = await db.scalar(
        select(Referral).where(Referral.referred_customer_id == customer_id, Referral.status == "pending")
    )
    if referral:
        referral.status = "converted"
        referral.policy_id = policy_id
        await db.commit()
