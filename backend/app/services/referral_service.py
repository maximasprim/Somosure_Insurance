import random
import string

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
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


async def redeem_referral_code(db: AsyncSession, code: str, new_customer_id: str) -> Referral | None:
    """Links a new customer to the referral that brought them in. Doesn't
    mark it 'converted' yet - conversion means the referred customer's
    first policy issues (see mark_converted_if_referred, called from
    policy_service.issue_policy), not just registering."""
    referral = await db.scalar(select(Referral).where(Referral.code == code, Referral.status == "pending"))
    if not referral:
        return None
    if str(referral.referrer_customer_id) == new_customer_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot refer yourself")

    referral.referred_customer_id = new_customer_id
    await db.commit()
    await db.refresh(referral)
    return referral


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
