"""Referral discount credits: cheaper insurance for an existing customer who
referred someone that bought a policy.

  * granted automatically when the referred customer's policy is issued (if the
    program setting says existing customers are rewarded with a discount), or by
    staff by hand;
  * does nothing until STAFF apply it, case by case, to one of that customer's
    applications - the amount is then taken off what they pay (payment_service);
  * can be released again (before any payment), cancelled, or expire.

Every step is on the audit trail (who, when, and the reason given).
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.affiliate import ReferralDiscount
from app.models.application import Application
from app.models.customer import Customer
from app.models.financing import FinancingApplication
from app.models.payment import Payment
from app.models.policy import Policy
from app.models.quote import Quote
from app.services.affiliate_service import eligible_referral, get_affiliate_settings, is_existing_customer
from app.services.discount_math import compute_discount

logger = logging.getLogger("somosure.referral_discount")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def effective_status(credit: ReferralDiscount) -> str:
    """'available' becomes 'expired' once its date passes (no background job needed)."""
    if credit.status == "available" and credit.expires_at and credit.expires_at < _now():
        return "expired"
    return credit.status


def describe(credit: ReferralDiscount) -> str:
    if credit.discount_type == "percent":
        text = f"{Decimal(credit.discount_value).normalize():f}% off"  # 12.00 -> "12", 7.50 -> "7.5"
    else:
        text = f"KES {Decimal(credit.discount_value):,.0f} off"
    return text + (f" (up to KES {Decimal(credit.max_amount):,.0f})" if credit.max_amount is not None else "")


def _need_reason(reason: str | None) -> str:
    text = (reason or "").strip()
    if len(text) < 3:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Please give a reason (at least a few words).")
    return text


# ----------------------------------------------------------------- granting


async def grant_discount_for_policy(db: AsyncSession, policy_id: Any) -> ReferralDiscount | None:
    """Called when a policy is issued: if its buyer was referred by an existing
    customer and the program rewards existing customers with a discount, create
    that customer's credit. Safe to call twice for the same policy."""
    settings = await get_affiliate_settings(db)
    if not settings.program_enabled or settings.existing_customer_reward not in ("discount", "both"):
        return None
    if Decimal(settings.discount_value or 0) <= 0:
        return None

    policy = await db.get(Policy, policy_id)
    if not policy:
        return None
    if await db.scalar(select(ReferralDiscount.id).where(ReferralDiscount.source_policy_id == policy.id)):
        return None
    if settings.min_premium is not None and Decimal(policy.premium or 0) < Decimal(settings.min_premium):
        return None

    referral = await eligible_referral(db, settings, policy)
    if not referral or not await is_existing_customer(db, referral.referrer_customer_id):
        return None

    buyer = await db.get(Customer, policy.customer_id)
    credit = ReferralDiscount(
        customer_id=referral.referrer_customer_id,
        referral_id=referral.id,
        source="referral",
        source_policy_id=policy.id,
        discount_type=settings.discount_type,
        discount_value=settings.discount_value,
        max_amount=settings.discount_max_amount,
        expires_at=_now() + timedelta(days=int(settings.discount_valid_days or 365)),
        status="available",
        note=f"Earned because {buyer.full_name if buyer else 'a referred customer'} bought policy {policy.policy_number}",
        created_by="system",
    )
    db.add(credit)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()  # a second request got there first - one credit per policy
        return None
    await db.refresh(credit)
    return credit


async def grant_manual(
    db: AsyncSession,
    customer_id: Any,
    discount_type: str,
    value: Decimal,
    max_amount: Decimal | None,
    valid_days: int | None,
    reason: str | None,
    user_id: str,
) -> ReferralDiscount:
    """Staff give a customer a discount credit directly (e.g. a goodwill gesture)."""
    if not await db.get(Customer, customer_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")
    credit = ReferralDiscount(
        customer_id=customer_id,
        source="manual",
        discount_type=discount_type,
        discount_value=value,
        max_amount=max_amount,
        expires_at=_now() + timedelta(days=valid_days) if valid_days else None,
        status="available",
        note=_need_reason(reason),
        created_by=user_id,
    )
    db.add(credit)
    await db.commit()
    await db.refresh(credit)
    return credit


# ------------------------------------------------------------ applying it


async def _application_facts(db: AsyncSession, application: Application) -> dict:
    """What decides whether (and how much) a discount can be applied to this application."""
    quote = await db.get(Quote, application.quote_id)
    paid = await db.scalar(
        select(func.count()).select_from(Payment).where(Payment.application_id == application.id, Payment.status == "successful")
    )
    has_policy = await db.scalar(select(Policy.id).where(Policy.application_id == application.id).limit(1))
    financed = await db.scalar(
        select(FinancingApplication.id)
        .where(
            FinancingApplication.quote_id == application.quote_id,
            FinancingApplication.status.notin_(("rejected", "eligibility_checked", "cancelled")),
        )
        .limit(1)
    )
    blocked = None
    if not quote:
        blocked = "The quote for this application is missing"
    elif application.status == "rejected":
        blocked = "This application was rejected"
    elif paid or has_policy:
        blocked = "Already paid - the policy is issued"
    elif application.discount_amount and Decimal(application.discount_amount) > 0:
        blocked = "A discount is already applied"
    elif financed:
        blocked = "Being paid through Bidii Credit financing - discounts aren't supported on financed premiums yet"
    return {"quote": quote, "blocked_reason": blocked}


async def eligible_applications(db: AsyncSession, credit: ReferralDiscount) -> list[dict]:
    """The customer's recent applications, each with the most this credit could
    take off it - or the reason it can't be applied."""
    rows = (
        await db.scalars(
            select(Application).where(Application.customer_id == credit.customer_id).order_by(Application.created_at.desc()).limit(20)
        )
    ).all()
    out = []
    for application in rows:
        facts = await _application_facts(db, application)
        quote = facts["quote"]
        max_discount = (
            compute_discount(credit.discount_type, credit.discount_value, credit.max_amount, quote.premium, quote.total) if quote else Decimal("0")
        )
        out.append(
            {
                "application_id": application.id,
                "reference": application.reference,
                "status": application.status,
                "premium": quote.premium if quote else Decimal("0"),
                "total": quote.total if quote else Decimal("0"),
                "max_discount": max_discount,
                "eligible": facts["blocked_reason"] is None and max_discount > 0,
                "blocked_reason": facts["blocked_reason"],
            }
        )
    return out


async def apply_credit(
    db: AsyncSession, credit_id: Any, application_id: Any, user_id: str, reason: str | None, amount: Decimal | None = None
) -> ReferralDiscount:
    credit = await db.get(ReferralDiscount, credit_id)
    if not credit:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Discount credit not found")
    if effective_status(credit) != "available":
        raise HTTPException(status.HTTP_409_CONFLICT, f"This credit can't be applied (it is {effective_status(credit)}).")
    application = await db.get(Application, application_id)
    if not application:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    if str(application.customer_id) != str(credit.customer_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "A credit can only be applied to the same customer's own application.")
    reason = _need_reason(reason)

    facts = await _application_facts(db, application)
    if facts["blocked_reason"]:
        raise HTTPException(status.HTTP_409_CONFLICT, facts["blocked_reason"])
    quote = facts["quote"]
    most = compute_discount(credit.discount_type, credit.discount_value, credit.max_amount, quote.premium, quote.total)
    if most <= 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "This credit is worth nothing on this application.")
    chosen = Decimal(amount) if amount is not None else most
    if chosen <= 0 or chosen > most:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"The discount must be between KES 0.01 and KES {most:,.2f} for this application.")

    now = _now()
    application.discount_amount = chosen
    application.discount_credit_id = credit.id
    application.discount_note = reason[:255]
    credit.status = "applied"
    credit.applied_application_id = application.id
    credit.applied_amount = chosen
    credit.applied_at = now
    credit.applied_by = user_id
    credit.status_note = reason
    await db.commit()
    await db.refresh(credit)
    return credit


async def release_credit(db: AsyncSession, credit_id: Any, user_id: str, reason: str | None) -> ReferralDiscount:
    """Takes an applied discount back off its application (only while nothing has
    been paid on it) and returns the credit to the customer."""
    credit = await db.get(ReferralDiscount, credit_id)
    if not credit:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Discount credit not found")
    if credit.status != "applied" or not credit.applied_application_id:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Only an applied credit can be released (this one is {credit.status}).")
    reason = _need_reason(reason)
    paid = await db.scalar(
        select(func.count()).select_from(Payment).where(
            Payment.application_id == credit.applied_application_id, Payment.status == "successful"
        )
    )
    if paid:
        raise HTTPException(status.HTTP_409_CONFLICT, "A payment has already been made with this discount, so it can't be released.")
    application = await db.get(Application, credit.applied_application_id)
    if application:
        application.discount_amount = None
        application.discount_credit_id = None
        application.discount_note = None
    credit.status = "available"
    credit.applied_application_id = None
    credit.applied_amount = None
    credit.applied_at = None
    credit.applied_by = None
    credit.status_note = f"Released: {reason}"
    await db.commit()
    await db.refresh(credit)
    return credit


async def cancel_credit(db: AsyncSession, credit_id: Any, user_id: str, reason: str | None) -> ReferralDiscount:
    credit = await db.get(ReferralDiscount, credit_id)
    if not credit:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Discount credit not found")
    if credit.status != "available":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Only an available credit can be cancelled (this one is {effective_status(credit)}).")
    credit.status = "cancelled"
    credit.status_note = _need_reason(reason)
    await db.commit()
    await db.refresh(credit)
    return credit


# --------------------------------------------------------------- read helpers


async def application_discount(db: AsyncSession, application_id: Any) -> dict:
    application = await db.get(Application, application_id)
    if not application:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    amount = Decimal(application.discount_amount) if application.discount_amount else None
    return {"discount_amount": amount if amount and amount > 0 else None, "note": application.discount_note if amount else None}
