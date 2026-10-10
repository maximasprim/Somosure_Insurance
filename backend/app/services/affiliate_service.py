"""The affiliate program: who earns what when someone they referred buys insurance.

Flow
----
  1. A customer shares a referral code (single-use) or, if enrolled as an
     affiliate, their reusable affiliate code. The new customer is linked to
     the referrer ("attribution", see referral_service.attribute_referrer).
  2. When that customer's policy is issued, record_commission_for_policy()
     works out the commission from the admin-configured rates
     (affiliate_rates.py) and records it as PENDING.
  3. A person approves it, then marks it paid with the payout reference - or
     rejects / reverses it with a reason. Every step is on the audit trail.

The rate that applied is copied onto the commission, so changing rates later
never changes what was already earned.
"""

import logging
import random
import string
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.affiliate import (
    AFFILIATE_SETTINGS_ID,
    Affiliate,
    AffiliateCommission,
    AffiliateRateRule,
    AffiliateSettings,
    ReferralDiscount,
)
from app.models.application import Application
from app.models.customer import Customer
from app.models.policy import Policy
from app.models.quote import Quote, QuoteRequest
from app.models.referral import Referral
from app.services.affiliate_rates import RateChoice, add_months, compute_amount, pick_rate
from app.services.product_catalog import normalize_category

logger = logging.getLogger("somosure.affiliate")

UNPAID_OR_VOID = ("reversed", "rejected")


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------ settings


async def get_affiliate_settings(db: AsyncSession) -> AffiliateSettings:
    """The program's one row of settings, created OFF with a 0% rate the first
    time it is read (so a fresh database behaves like "no program")."""
    row = await db.get(AffiliateSettings, AFFILIATE_SETTINGS_ID)
    if not row:
        row = AffiliateSettings(
            id=AFFILIATE_SETTINGS_ID,
            program_enabled=False,
            default_rate_type="percent",
            default_rate_value=Decimal("0.00"),
            scope="first_policy",
            window_months=12,
            auto_approve=False,
            allow_self_enrollment=False,
            existing_customer_reward="commission",
            discount_type="percent",
            discount_value=Decimal("0.00"),
            discount_valid_days=365,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return row


# --------------------------------------------------------------- rate lookup


async def is_existing_customer(db: AsyncSession, customer_id: Any) -> bool:
    """An 'existing customer' has at least one policy with us that is in force
    right now (active, and not past its end date)."""
    if not customer_id:
        return False
    found = await db.scalar(
        select(Policy.id)
        .where(Policy.customer_id == customer_id, Policy.status == "active", Policy.end_date >= date.today())
        .limit(1)
    )
    return found is not None


async def resolve_rate(db: AsyncSession, referrer_customer_id: Any, category: str | None, settings: AffiliateSettings | None = None) -> RateChoice:
    settings = settings or await get_affiliate_settings(db)
    rules = (await db.scalars(select(AffiliateRateRule))).all()
    existing_value = settings.existing_customer_rate_value
    return pick_rate(
        rules,
        referrer_id=str(referrer_customer_id) if referrer_customer_id else None,
        category=normalize_category(category) if category else None,
        today=date.today(),
        default_type=settings.default_rate_type,
        default_value=Decimal(settings.default_rate_value),
        referrer_is_customer=await is_existing_customer(db, referrer_customer_id),
        existing_customer_type=settings.existing_customer_rate_type,
        existing_customer_value=Decimal(existing_value) if existing_value is not None else None,
    )


async def preview_commission(db: AsyncSession, referrer_customer_id: Any, category: str | None, premium: Decimal) -> dict:
    """What a referrer would earn on a policy of this size - for the admin 'try it' box."""
    settings = await get_affiliate_settings(db)
    choice = await resolve_rate(db, referrer_customer_id, category, settings)
    amount = compute_amount(choice, premium, global_cap=settings.max_commission_per_policy)
    below_min = settings.min_premium is not None and Decimal(premium) < Decimal(settings.min_premium)
    return {
        "program_enabled": settings.program_enabled,
        "rate_type": choice.rate_type,
        "rate_value": str(choice.rate_value),
        "rate_label": choice.label,
        "amount": str(Decimal("0.00") if below_min else amount),
        "below_minimum_premium": below_min,
        "referrer_is_existing_customer": await is_existing_customer(db, referrer_customer_id),
    }


# ------------------------------------------------------ recording commissions


async def _category_for_policy(db: AsyncSession, policy: Policy) -> str | None:
    application = await db.get(Application, policy.application_id)
    quote = await db.get(Quote, application.quote_id) if application else None
    request = await db.get(QuoteRequest, quote.quote_request_id) if quote else None
    return normalize_category(request.category) if request and request.category else None


async def _sync_referral(db: AsyncSession, referral: Referral) -> None:
    """Keeps the older referral fields (reward_amount / reward_paid / status)
    in step with the commissions, so existing screens and reports still make sense."""
    await db.flush()
    total = await db.scalar(
        select(func.coalesce(func.sum(AffiliateCommission.commission_amount), 0)).where(
            AffiliateCommission.referral_id == referral.id, AffiliateCommission.status.notin_(UNPAID_OR_VOID)
        )
    )
    paid = await db.scalar(
        select(func.count()).select_from(AffiliateCommission).where(
            AffiliateCommission.referral_id == referral.id, AffiliateCommission.status == "paid"
        )
    )
    referral.reward_amount = Decimal(total or 0)
    referral.reward_paid = bool(paid)
    if paid:
        referral.status = "rewarded"
    elif referral.status == "rewarded":
        referral.status = "converted"


async def eligible_referral(db: AsyncSession, settings: AffiliateSettings, policy: Policy) -> Referral | None:
    """The referral that should be rewarded for this policy, or None. Shared by
    commissions and discount credits so both follow the same rules: the buyer
    was referred, not by themselves, the referrer isn't a paused affiliate, and
    the program's scope (first policy only, or every policy within the window)
    allows it."""
    referral = await db.scalar(
        select(Referral).where(Referral.referred_customer_id == policy.customer_id).order_by(Referral.created_at.asc()).limit(1)
    )
    if not referral or str(referral.referrer_customer_id) == str(policy.customer_id):
        return None

    affiliate = await db.scalar(select(Affiliate).where(Affiliate.customer_id == referral.referrer_customer_id))
    if affiliate and affiliate.status == "suspended":
        return None

    if settings.scope == "first_policy":
        # Anything already awarded for this referral on a DIFFERENT policy means
        # the first policy has been and gone. (A removed policy leaves a null link.)
        other_commissions = await db.scalar(
            select(func.count()).select_from(AffiliateCommission).where(
                AffiliateCommission.referral_id == referral.id,
                or_(AffiliateCommission.policy_id.is_(None), AffiliateCommission.policy_id != policy.id),
            )
        )
        other_credits = await db.scalar(
            select(func.count()).select_from(ReferralDiscount).where(
                ReferralDiscount.referral_id == referral.id,
                or_(ReferralDiscount.source_policy_id.is_(None), ReferralDiscount.source_policy_id != policy.id),
            )
        )
        # (ids compared as text: the link may have just been set from a string)
        if other_commissions or other_credits or (referral.policy_id is not None and str(referral.policy_id) != str(policy.id)):
            return None
    elif settings.window_months:
        started = referral.referred_at or referral.created_at
        if _now() > add_months(started, int(settings.window_months)):
            return None
    return referral


async def record_commission_for_policy(db: AsyncSession, policy_id: Any) -> AffiliateCommission | None:
    """Called when a policy is issued. Creates the referrer's commission if the
    program is on and every rule is met; otherwise does nothing. Safe to call
    twice for the same policy."""
    settings = await get_affiliate_settings(db)
    if not settings.program_enabled:
        return None

    policy = await db.get(Policy, policy_id)
    if not policy:
        return None
    if await db.scalar(select(AffiliateCommission.id).where(AffiliateCommission.policy_id == policy.id)):
        return None

    referral = await eligible_referral(db, settings, policy)
    if not referral:
        return None

    # When existing customers are rewarded with a discount INSTEAD of cash,
    # they don't also earn commission.
    if settings.existing_customer_reward == "discount" and await is_existing_customer(db, referral.referrer_customer_id):
        return None

    premium = Decimal(policy.premium or 0)
    if settings.min_premium is not None and premium < Decimal(settings.min_premium):
        return None

    category = await _category_for_policy(db, policy)
    choice = await resolve_rate(db, referral.referrer_customer_id, category, settings)
    amount = compute_amount(choice, premium, global_cap=settings.max_commission_per_policy)
    if amount <= 0:
        return None

    now = _now()
    auto = bool(settings.auto_approve)
    commission = AffiliateCommission(
        referral_id=referral.id,
        referrer_customer_id=referral.referrer_customer_id,
        referred_customer_id=policy.customer_id,
        policy_id=policy.id,
        category=category,
        premium=premium,
        rate_type=choice.rate_type,
        rate_value=choice.rate_value,
        rate_label=(choice.label or "")[:120],
        commission_amount=amount,
        status="approved" if auto else "pending",
        approved_at=now if auto else None,
        approved_by="auto-approved" if auto else None,
    )
    db.add(commission)
    try:
        await _sync_referral(db, referral)
        await db.commit()
    except IntegrityError:
        # A second request raced us to the same policy - the unique constraint
        # on policy_id guarantees only one commission, so this is fine.
        await db.rollback()
        return None
    await db.refresh(commission)
    return commission


# ----------------------------------------------------------- admin decisions


async def _get_commission(db: AsyncSession, commission_id: Any) -> AffiliateCommission:
    commission = await db.get(AffiliateCommission, commission_id)
    if not commission:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Commission not found")
    return commission


def _need_reason(reason: str | None) -> str:
    text = (reason or "").strip()
    if len(text) < 3:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Please give a reason (at least a few words).")
    return text


async def _finish(db: AsyncSession, commission: AffiliateCommission) -> AffiliateCommission:
    referral = await db.get(Referral, commission.referral_id)
    if referral:
        await _sync_referral(db, referral)
    await db.commit()
    await db.refresh(commission)
    return commission


async def approve_commission(db: AsyncSession, commission_id: Any, user_id: str) -> AffiliateCommission:
    commission = await _get_commission(db, commission_id)
    if commission.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Only pending commissions can be approved (this one is {commission.status}).")
    commission.status = "approved"
    commission.approved_at = _now()
    commission.approved_by = user_id
    return await _finish(db, commission)


async def pay_commission(db: AsyncSession, commission_id: Any, user_id: str, reference: str, method: str | None) -> AffiliateCommission:
    commission = await _get_commission(db, commission_id)
    if commission.status != "approved":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Only approved commissions can be marked paid (this one is {commission.status}).")
    reference = (reference or "").strip()
    if not reference:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Enter the payout reference (e.g. the M-Pesa transaction code).")
    commission.status = "paid"
    commission.paid_at = _now()
    commission.paid_by = user_id
    commission.payout_reference = reference[:120]
    commission.payout_method = (method or "mpesa")[:20]
    return await _finish(db, commission)


async def reject_commission(db: AsyncSession, commission_id: Any, user_id: str, reason: str | None) -> AffiliateCommission:
    commission = await _get_commission(db, commission_id)
    if commission.status not in ("pending", "approved"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"A {commission.status} commission can't be rejected.")
    commission.status = "rejected"
    commission.status_note = _need_reason(reason)
    return await _finish(db, commission)


async def reverse_commission(db: AsyncSession, commission_id: Any, user_id: str, reason: str | None) -> AffiliateCommission:
    """Takes back an approved or already-paid commission (cancelled policy, refund, fraud...)."""
    commission = await _get_commission(db, commission_id)
    if commission.status not in ("approved", "paid"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Only approved or paid commissions can be reversed (this one is {commission.status}).")
    commission.status = "reversed"
    commission.status_note = _need_reason(reason)
    return await _finish(db, commission)


# ---------------------------------------------------------------- affiliates


def generate_affiliate_code() -> str:
    return "AFF" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


async def enroll_affiliate(db: AsyncSession, customer_id: Any, notes: str | None = None) -> Affiliate:
    existing = await db.scalar(select(Affiliate).where(Affiliate.customer_id == customer_id))
    if existing:
        return existing
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")
    code = generate_affiliate_code()
    while await db.scalar(select(Affiliate.id).where(Affiliate.code == code)) or await db.scalar(
        select(Referral.id).where(Referral.code == code)
    ):
        code = generate_affiliate_code()
    affiliate = Affiliate(customer_id=customer.id, code=code, status="active", payout_phone=customer.phone, notes=notes)
    db.add(affiliate)
    await db.commit()
    await db.refresh(affiliate)
    return affiliate


# --------------------------------------------------------------------- stats


async def earnings_by_status(db: AsyncSession, referrer_customer_id: Any) -> dict[str, Decimal]:
    rows = (
        await db.execute(
            select(AffiliateCommission.status, func.coalesce(func.sum(AffiliateCommission.commission_amount), 0))
            .where(AffiliateCommission.referrer_customer_id == referrer_customer_id)
            .group_by(AffiliateCommission.status)
        )
    ).all()
    return {status_: Decimal(total) for status_, total in rows}


async def referral_counts(db: AsyncSession, referrer_customer_id: Any) -> dict[str, int]:
    referred, converted = (
        await db.execute(
            select(
                func.count(Referral.id),
                func.coalesce(func.sum(case((Referral.status.in_(("converted", "rewarded")), 1), else_=0)), 0),
            ).where(Referral.referrer_customer_id == referrer_customer_id, Referral.referred_customer_id.is_not(None))
        )
    ).one()
    return {"referred": int(referred or 0), "converted": int(converted or 0)}


async def record_rewards_for_policy(db: AsyncSession, policy_id: Any) -> None:
    """Everything a referrer can earn when the referred customer's policy is
    issued: cash commission and/or a discount credit, per the program settings.
    Each part is independent - a problem in one never stops the other."""
    try:
        await record_commission_for_policy(db, policy_id)
    except Exception:
        logger.exception("Could not record affiliate commission for policy %s", policy_id)
        await db.rollback()
    try:
        from app.services.referral_discount_service import grant_discount_for_policy

        await grant_discount_for_policy(db, policy_id)
    except Exception:
        logger.exception("Could not grant a referral discount for policy %s", policy_id)
        await db.rollback()
