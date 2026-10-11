"""Partner applications: the public 'Become a partner' form, the staff decision
(with a reason), and what approving does.

Approving, in one step and one database transaction:
  1. creates the Partner record (managed by the person who approved it);
  2. optionally enrols the contact person as an AFFILIATE (a reusable referral
     link and code), creating their customer record if they don't have one;
  3. optionally gives that affiliate a special commission rate and/or an
     insurance discount credit.
Declining records the reason and creates nothing.
"""

import logging
import random
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.phone import phone_variants
from app.models.affiliate import Affiliate, AffiliateRateRule, ReferralDiscount
from app.models.customer import Customer
from app.models.partner import Partner, PartnerApplication
from app.models.referral import Referral
from app.schemas.partner_application import ApproveIn, PartnerApplicationIn
from app.services.affiliate_service import generate_affiliate_code, get_affiliate_settings

logger = logging.getLogger("somosure.partner_applications")

TYPE_LABELS = {
    "car_dealer": "Car dealer", "vehicle_importer": "Vehicle importer", "employer": "Employer", "sme": "Small business (SME)",
    "bank": "Bank", "sacco": "SACCO", "agent": "Agent", "corporate": "Corporate",
}
MODEL_LABELS = {
    "referrals": "Referring customers to us",
    "applications": "Submitting applications for their customers",
    "both": "Both - referring and submitting applications",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _frontend_base() -> str:
    value = get_settings().frontend_base_url
    if isinstance(value, (tuple, list)):  # tolerate a comma slipped into the setting
        value = value[0] if value else ""
    return str(value).split(",")[0].strip().rstrip("/")


async def _new_reference(db: AsyncSession) -> str:
    while True:
        reference = f"SOM-PTR-{_now().year}-{random.randint(0, 999999):06d}"
        if not await db.scalar(select(PartnerApplication.id).where(PartnerApplication.reference == reference)):
            return reference


# ---------------------------------------------------------------- submitting


async def submit_application(db: AsyncSession, data: PartnerApplicationIn) -> tuple[PartnerApplication, bool]:
    """Stores a new application. Returns (application, is_new).

    The same person sending the form twice (a double-click, a retry) doesn't
    create a second application or alert the team twice: if a PENDING
    application already exists for that email or phone, it is returned."""
    existing = await db.scalar(
        select(PartnerApplication)
        .where(
            PartnerApplication.status == "pending",
            (func.lower(PartnerApplication.contact_email) == data.contact_email)
            | PartnerApplication.contact_phone.in_(phone_variants(data.contact_phone)),
        )
        .order_by(PartnerApplication.created_at.asc())
        .limit(1)
    )
    if existing:
        return existing, False

    application = PartnerApplication(
        reference=await _new_reference(db),
        business_name=data.business_name,
        partner_type=data.partner_type,
        contact_name=data.contact_name,
        contact_email=data.contact_email,
        contact_phone=data.contact_phone,
        town=data.town or None,
        website=data.website or None,
        working_model=data.working_model,
        monthly_clients=data.monthly_clients,
        products=data.products or None,
        message=data.message,
        status="pending",
    )
    db.add(application)
    await db.commit()
    await db.refresh(application)
    return application, True


# --------------------------------------------------------------------- alerts


def alert_text(application: PartnerApplication | dict) -> tuple[str, str, str]:
    """(email subject, email body, short SMS) announcing a new application."""
    a = application if isinstance(application, dict) else {
        "reference": application.reference, "business_name": application.business_name,
        "partner_type": application.partner_type, "contact_name": application.contact_name,
        "contact_email": application.contact_email, "contact_phone": application.contact_phone,
        "town": application.town, "working_model": application.working_model,
        "monthly_clients": application.monthly_clients, "products": application.products, "message": application.message,
    }
    kind = TYPE_LABELS.get(a["partner_type"], a["partner_type"])
    link = f"{_frontend_base()}/admin/partner-applications"
    subject = f"New partner application: {a['business_name']} ({kind})"
    body = (
        f"{a['business_name']} has applied to become a Somosure partner.\n\n"
        f"Reference: {a['reference']}\n"
        f"Type: {kind}\n"
        f"Contact: {a['contact_name']} - {a['contact_phone']} - {a['contact_email']}\n"
        f"Town: {a.get('town') or '-'}\n"
        f"Would like to: {MODEL_LABELS.get(a['working_model'], a['working_model'])}\n"
        f"Expected customers a month: {a['monthly_clients']}\n"
        f"Products of interest: {', '.join(a.get('products') or []) or '-'}\n\n"
        f"What they said:\n{a['message']}\n\n"
        f"Review it here: {link}\n"
    )
    sms = f"New partner application: {a['business_name']} ({kind}), {a['contact_name']} {a['contact_phone']}. Ref {a['reference']}."
    return subject, body, sms


def snapshot(application: PartnerApplication) -> dict:
    """Plain data for the alert, so it can be sent after the request ends
    without touching the database again."""
    return {
        "reference": application.reference, "business_name": application.business_name,
        "partner_type": application.partner_type, "contact_name": application.contact_name,
        "contact_email": application.contact_email, "contact_phone": application.contact_phone,
        "town": application.town, "working_model": application.working_model,
        "monthly_clients": application.monthly_clients, "products": application.products, "message": application.message,
    }


async def alert_team(application: dict) -> None:
    """Emails (and texts) the people named in PARTNER_ALERT_EMAILS / _PHONES.
    Best effort: it runs after the applicant has already been answered, and any
    failure is only logged - the application is safely stored either way. With
    nothing configured it logs the alert (the admin queue still shows it)."""
    from app.notifications.registry import get_dispatcher, get_email_dispatcher

    settings = get_settings()
    subject, body, sms = alert_text(application)
    emails = [e.strip() for e in (settings.partner_alert_emails or "").split(",") if e.strip()]
    phones = [p.strip() for p in (settings.partner_alert_phones or "").split(",") if p.strip()]
    if not emails and not phones:
        logger.info("[PARTNER APPLICATION] %s - no PARTNER_ALERT_EMAILS/PHONES configured; see the admin queue", subject)
        return
    for email in emails:
        try:
            await get_email_dispatcher().send_email(email, subject, body)
        except Exception:
            logger.exception("Could not email the partner-application alert to %s", email)
    for phone in phones:
        try:
            await get_dispatcher().send_sms(phone, sms)
        except Exception:
            logger.exception("Could not text the partner-application alert to %s", phone)


# ------------------------------------------------------------------ deciding


async def _get(db: AsyncSession, application_id: Any) -> PartnerApplication:
    application = await db.get(PartnerApplication, application_id)
    if not application:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    return application


async def decline_application(db: AsyncSession, application_id: Any, user_id: str, reason: str) -> PartnerApplication:
    application = await _get(db, application_id)
    if application.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, f"This application has already been {application.status}.")
    application.status = "declined"
    application.decision_reason = reason.strip()
    application.decided_by = user_id
    application.decided_at = _now()
    await db.commit()
    await db.refresh(application)
    return application


async def approve_application(db: AsyncSession, application_id: Any, user_id: str, payload: ApproveIn) -> dict:
    application = await _get(db, application_id)
    if application.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, f"This application has already been {application.status}.")

    wants_extras = any(v is not None for v in (payload.commission_value, payload.discount_value))
    if wants_extras and not payload.enrol_affiliate:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Turn on 'enrol as an affiliate' to give a commission rate or a discount.")
    if (payload.commission_value is None) != (payload.commission_type is None):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Give both the commission type and its value, or neither.")
    if (payload.discount_value is None) != (payload.discount_type is None):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Give both the discount type and its value, or neither.")
    if payload.commission_type == "percent" and payload.commission_value is not None and payload.commission_value > 100:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A percentage commission can't be more than 100.")
    if payload.discount_type == "percent" and payload.discount_value is not None and payload.discount_value > 100:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A percentage discount can't be more than 100.")

    now = _now()
    warnings: list[str] = []
    try:
        managed_by = uuid.UUID(str(user_id))
    except ValueError:
        managed_by = None

    partner = Partner(
        name=application.business_name,
        partner_type=payload.partner_type or application.partner_type,
        contact_name=application.contact_name,
        contact_email=application.contact_email,
        contact_phone=application.contact_phone,
        is_active=True,
        managed_by_user_id=managed_by,
    )
    db.add(partner)
    await db.flush()

    affiliate_code = None
    commission_rule_created = False
    discount_credit_created = False
    if payload.enrol_affiliate:
        customer = await db.scalar(
            select(Customer).where(Customer.phone.in_(phone_variants(application.contact_phone))).order_by(Customer.created_at.asc())
        ) or await db.scalar(select(Customer).where(func.lower(Customer.email) == application.contact_email).order_by(Customer.created_at.asc()))
        if not customer:
            customer = Customer(
                full_name=application.contact_name, phone=application.contact_phone, email=application.contact_email,
                lead_source="partner_application",
            )
            db.add(customer)
            await db.flush()

        affiliate = await db.scalar(select(Affiliate).where(Affiliate.customer_id == customer.id))
        if not affiliate:
            code = generate_affiliate_code()
            while await db.scalar(select(Affiliate.id).where(Affiliate.code == code)) or await db.scalar(select(Referral.id).where(Referral.code == code)):
                code = generate_affiliate_code()
            affiliate = Affiliate(
                customer_id=customer.id, code=code, status="active", payout_phone=customer.phone,
                notes=f"Enrolled with partner application {application.reference} ({application.business_name})",
            )
            db.add(affiliate)
            await db.flush()
        affiliate_code = affiliate.code
        application.customer_id = customer.id

        if payload.commission_value is not None:
            db.add(
                AffiliateRateRule(
                    name=f"Partner rate: {application.business_name}"[:120],
                    rate_type=payload.commission_type,
                    rate_value=payload.commission_value,
                    affiliate_customer_id=customer.id,
                    active=True,
                )
            )
            commission_rule_created = True
        if payload.discount_value is not None:
            db.add(
                ReferralDiscount(
                    customer_id=customer.id,
                    source="manual",
                    discount_type=payload.discount_type,
                    discount_value=payload.discount_value,
                    expires_at=now + timedelta(days=payload.discount_valid_days or 365),
                    status="available",
                    note=f"Partner discount for {application.business_name} ({application.reference})",
                    created_by=str(user_id),
                )
            )
            discount_credit_created = True

        if not (await get_affiliate_settings(db)).program_enabled:
            warnings.append("The affiliate program is switched off, so no commission is earned yet - switch it on in Affiliates → Rates & settings.")

    application.status = "approved"
    application.decision_reason = payload.reason.strip()
    application.decided_by = str(user_id)
    application.decided_at = now
    application.partner_id = partner.id
    application.affiliate_code = affiliate_code
    await db.commit()
    await db.refresh(application)

    return {
        "application": application,
        "partner_id": partner.id,
        "affiliate_code": affiliate_code,
        "affiliate_link_path": f"/?ref={affiliate_code}" if affiliate_code else None,
        "commission_rule_created": commission_rule_created,
        "discount_credit_created": discount_credit_created,
        "warnings": warnings,
    }
