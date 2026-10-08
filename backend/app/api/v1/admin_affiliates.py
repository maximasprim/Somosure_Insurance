"""Admin side of the affiliate program: settings, commission rates, affiliates
and the commission queue. Everything here lands on the audit trail with who,
when and (when given) why."""

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_claims, require_roles
from app.models.affiliate import Affiliate, AffiliateCommission, AffiliateRateRule
from app.models.customer import Customer
from app.models.policy import Policy
from app.models.referral import Referral
from app.schemas.affiliate import (
    AffiliateOut,
    AffiliateSettingsOut,
    AffiliateSettingsUpdate,
    AffiliateUpdate,
    BulkIn,
    BulkResult,
    CommissionOut,
    CommissionPage,
    EnrollIn,
    PayIn,
    RateRuleIn,
    RateRuleOut,
    RateRuleUpdate,
    ReasonIn,
    SummaryOut,
)
from app.services import affiliate_service as svc

router = APIRouter(prefix="/api/v1/admin/affiliate-program", tags=["admin-affiliates"])

CONFIGURE = require_roles("super_admin", "management")
OPERATE = require_roles("super_admin", "management", "finance_officer")


# ---------------------------------------------------------------- settings


@router.get("/settings", response_model=AffiliateSettingsOut, dependencies=[Depends(OPERATE)])
async def get_settings(db: AsyncSession = Depends(get_db)):
    return await svc.get_affiliate_settings(db)


@router.patch("/settings", response_model=AffiliateSettingsOut, dependencies=[Depends(CONFIGURE)])
async def update_settings(payload: AffiliateSettingsUpdate, db: AsyncSession = Depends(get_db)):
    row = await svc.get_affiliate_settings(db)
    # Explicit nulls are meaningful for the two optional limits (they clear
    # them); every other field is only touched when sent.
    for key, value in payload.model_dump(exclude_unset=True).items():
        if value is None and key not in ("min_premium", "max_commission_per_policy"):
            continue
        setattr(row, key, value)
    await db.commit()
    await db.refresh(row)
    return row


# --------------------------------------------------------- customer finder


@router.get("/customers", dependencies=[Depends(OPERATE)])
async def find_customers(q: str = Query(min_length=2, max_length=60), db: AsyncSession = Depends(get_db)):
    """Small lookup used to pick a person for a rate rule, a preview or an
    enrolment: matches name, phone or email."""
    like = f"%{q.strip()}%"
    rows = (
        await db.scalars(
            select(Customer)
            .where(or_(Customer.full_name.ilike(like), Customer.phone.ilike(like), Customer.email.ilike(like)))
            .order_by(Customer.full_name)
            .limit(8)
        )
    ).all()
    return [{"id": str(c.id), "full_name": c.full_name, "phone": c.phone, "email": c.email} for c in rows]


# ------------------------------------------------------------- rate rules


async def _rule_out(db: AsyncSession, rule: AffiliateRateRule) -> RateRuleOut:
    name = None
    if rule.affiliate_customer_id:
        customer = await db.get(Customer, rule.affiliate_customer_id)
        name = customer.full_name if customer else None
    return RateRuleOut(
        id=rule.id, name=rule.name, rate_type=rule.rate_type, rate_value=rule.rate_value, max_amount=rule.max_amount,
        affiliate_customer_id=rule.affiliate_customer_id, affiliate_name=name, category=rule.category,
        starts_on=rule.starts_on, ends_on=rule.ends_on, active=rule.active, created_at=rule.created_at,
    )


def _check_dates(starts_on, ends_on) -> None:
    if starts_on and ends_on and ends_on < starts_on:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "The end date can't be before the start date.")


@router.get("/rules", response_model=list[RateRuleOut], dependencies=[Depends(OPERATE)])
async def list_rules(db: AsyncSession = Depends(get_db)):
    rules = (await db.scalars(select(AffiliateRateRule).order_by(AffiliateRateRule.created_at.desc()))).all()
    return [await _rule_out(db, r) for r in rules]


@router.post("/rules", response_model=RateRuleOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(CONFIGURE)])
async def create_rule(payload: RateRuleIn, db: AsyncSession = Depends(get_db)):
    _check_dates(payload.starts_on, payload.ends_on)
    if payload.rate_type == "percent" and payload.rate_value > 100:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A percentage rate can't be more than 100.")
    if payload.affiliate_customer_id and not await db.get(Customer, payload.affiliate_customer_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That customer doesn't exist.")
    rule = AffiliateRateRule(**payload.model_dump())
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return await _rule_out(db, rule)


@router.patch("/rules/{rule_id}", response_model=RateRuleOut, dependencies=[Depends(CONFIGURE)])
async def update_rule(rule_id: uuid.UUID, payload: RateRuleUpdate, db: AsyncSession = Depends(get_db)):
    rule = await db.get(AffiliateRateRule, rule_id)
    if not rule:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rule not found")
    changes = payload.model_dump(exclude_unset=True)
    # null clears these (e.g. "no end date", "applies to everyone")
    nullable = {"max_amount", "affiliate_customer_id", "category", "starts_on", "ends_on"}
    for key, value in changes.items():
        if value is None and key not in nullable:
            continue
        setattr(rule, key, value)
    _check_dates(rule.starts_on, rule.ends_on)
    if rule.rate_type == "percent" and Decimal(rule.rate_value) > 100:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A percentage rate can't be more than 100.")
    await db.commit()
    await db.refresh(rule)
    return await _rule_out(db, rule)


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(CONFIGURE)])
async def delete_rule(rule_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Removes the rule going forward. Commissions already earned keep the rate
    they were given (it is copied onto each one)."""
    rule = await db.get(AffiliateRateRule, rule_id)
    if not rule:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Rule not found")
    await db.delete(rule)
    await db.commit()


@router.get("/preview", dependencies=[Depends(OPERATE)])
async def preview(
    referrer_customer_id: uuid.UUID,
    premium: Decimal = Query(gt=0),
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """'What would this person earn?' - tries the current settings and rules
    without recording anything."""
    if not await db.get(Customer, referrer_customer_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")
    return await svc.preview_commission(db, referrer_customer_id, category, premium)


# --------------------------------------------------------------- affiliates


async def _affiliate_out(db: AsyncSession, affiliate: Affiliate) -> AffiliateOut:
    customer = await db.get(Customer, affiliate.customer_id)
    counts = await svc.referral_counts(db, affiliate.customer_id)
    earned = await svc.earnings_by_status(db, affiliate.customer_id)
    return AffiliateOut(
        id=affiliate.id, customer_id=affiliate.customer_id,
        customer_name=customer.full_name if customer else None, customer_phone=customer.phone if customer else None,
        code=affiliate.code, status=affiliate.status, payout_method=affiliate.payout_method,
        payout_phone=affiliate.payout_phone, notes=affiliate.notes,
        referred=counts["referred"], converted=counts["converted"],
        earned_pending=earned.get("pending", Decimal("0")), earned_approved=earned.get("approved", Decimal("0")),
        earned_paid=earned.get("paid", Decimal("0")), created_at=affiliate.created_at,
    )


@router.get("/partners", response_model=list[AffiliateOut], dependencies=[Depends(OPERATE)])
async def list_affiliates(q: str | None = None, db: AsyncSession = Depends(get_db)):
    stmt = select(Affiliate).join(Customer, Customer.id == Affiliate.customer_id).order_by(Affiliate.created_at.desc())
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Customer.full_name.ilike(like), Customer.phone.ilike(like), Affiliate.code.ilike(like)))
    rows = (await db.scalars(stmt.limit(200))).all()
    return [await _affiliate_out(db, a) for a in rows]


@router.post("/partners", response_model=AffiliateOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(CONFIGURE)])
async def enroll(payload: EnrollIn, db: AsyncSession = Depends(get_db)):
    """Enrols a customer as an affiliate (gives them a reusable code). Find the
    customer by id, email or phone."""
    customer = None
    if payload.customer_id:
        customer = await db.get(Customer, payload.customer_id)
    elif payload.email:
        customer = await db.scalar(select(Customer).where(func.lower(Customer.email) == payload.email.strip().lower()))
    elif payload.phone:
        from app.core.phone import phone_variants

        customer = await db.scalar(select(Customer).where(Customer.phone.in_(phone_variants(payload.phone))))
    else:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Give the customer's id, email or phone.")
    if not customer:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No customer found with those details.")
    affiliate = await svc.enroll_affiliate(db, customer.id, payload.notes)
    return await _affiliate_out(db, affiliate)


@router.patch("/partners/{affiliate_id}", response_model=AffiliateOut, dependencies=[Depends(CONFIGURE)])
async def update_affiliate(affiliate_id: uuid.UUID, payload: AffiliateUpdate, db: AsyncSession = Depends(get_db)):
    affiliate = await db.get(Affiliate, affiliate_id)
    if not affiliate:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Affiliate not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        if value is None and key != "notes":
            continue
        setattr(affiliate, key, value)
    await db.commit()
    await db.refresh(affiliate)
    return await _affiliate_out(db, affiliate)


# -------------------------------------------------------------- commissions


async def _commission_rows(db: AsyncSession, conds: list, limit: int, offset: int, q: str | None = None):
    referrer = aliased(Customer)
    referred = aliased(Customer)
    if q:
        like = f"%{q.strip()}%"
        conds = [*conds, or_(referrer.full_name.ilike(like), referrer.phone.ilike(like), AffiliateCommission.payout_reference.ilike(like))]
    base = (
        select(AffiliateCommission, referrer, referred, Policy.policy_number, Affiliate.payout_phone)
        .join(referrer, referrer.id == AffiliateCommission.referrer_customer_id)
        .join(referred, referred.id == AffiliateCommission.referred_customer_id)
        .outerjoin(Policy, Policy.id == AffiliateCommission.policy_id)
        .outerjoin(Affiliate, Affiliate.customer_id == AffiliateCommission.referrer_customer_id)
        .where(*conds)
    )
    total = await db.scalar(
        select(func.count()).select_from(AffiliateCommission)
        .join(referrer, referrer.id == AffiliateCommission.referrer_customer_id)
        .where(*conds)
    ) or 0
    rows = (await db.execute(base.order_by(AffiliateCommission.created_at.desc()).limit(limit).offset(offset))).all()
    items = [
        CommissionOut(
            id=c.id, referrer_customer_id=c.referrer_customer_id, referrer_name=r.full_name, referrer_phone=r.phone,
            payout_phone=payout_phone or r.phone, referred_name=d.full_name, policy_id=c.policy_id,
            policy_number=policy_number, category=c.category, premium=c.premium, rate_type=c.rate_type,
            rate_value=c.rate_value, rate_label=c.rate_label, commission_amount=c.commission_amount, status=c.status,
            status_note=c.status_note, approved_at=c.approved_at, paid_at=c.paid_at, payout_method=c.payout_method,
            payout_reference=c.payout_reference, created_at=c.created_at,
        )
        for c, r, d, policy_number, payout_phone in rows
    ]
    return items, total


@router.get("/commissions", response_model=CommissionPage, dependencies=[Depends(OPERATE)])
async def list_commissions(
    status_: str | None = Query(None, alias="status", pattern="^(pending|approved|paid|reversed|rejected)$"),
    referrer_customer_id: uuid.UUID | None = None,
    q: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    conds = []
    if status_:
        conds.append(AffiliateCommission.status == status_)
    if referrer_customer_id:
        conds.append(AffiliateCommission.referrer_customer_id == referrer_customer_id)
    items, total = await _commission_rows(db, conds, limit, offset, q)
    return CommissionPage(items=items, total=total, limit=limit, offset=offset)


async def _single(db: AsyncSession, commission_id: uuid.UUID) -> CommissionOut:
    items, _ = await _commission_rows(db, [AffiliateCommission.id == commission_id], 1, 0)
    return items[0]


def _user_id(claims: dict) -> str:
    return str(claims.get("sub"))


@router.post("/commissions/{commission_id}/approve", response_model=CommissionOut, dependencies=[Depends(OPERATE)])
async def approve(commission_id: uuid.UUID, db: AsyncSession = Depends(get_db), claims: dict = Depends(get_current_claims)):
    await svc.approve_commission(db, commission_id, _user_id(claims))
    return await _single(db, commission_id)


@router.post("/commissions/{commission_id}/pay", response_model=CommissionOut, dependencies=[Depends(OPERATE)])
async def pay(commission_id: uuid.UUID, payload: PayIn, db: AsyncSession = Depends(get_db), claims: dict = Depends(get_current_claims)):
    await svc.pay_commission(db, commission_id, _user_id(claims), payload.payout_reference, payload.payout_method)
    return await _single(db, commission_id)


@router.post("/commissions/{commission_id}/reject", response_model=CommissionOut, dependencies=[Depends(OPERATE)])
async def reject(commission_id: uuid.UUID, payload: ReasonIn, db: AsyncSession = Depends(get_db), claims: dict = Depends(get_current_claims)):
    await svc.reject_commission(db, commission_id, _user_id(claims), payload.reason)
    return await _single(db, commission_id)


@router.post("/commissions/{commission_id}/reverse", response_model=CommissionOut, dependencies=[Depends(OPERATE)])
async def reverse(commission_id: uuid.UUID, payload: ReasonIn, db: AsyncSession = Depends(get_db), claims: dict = Depends(get_current_claims)):
    await svc.reverse_commission(db, commission_id, _user_id(claims), payload.reason)
    return await _single(db, commission_id)


@router.post("/commissions/bulk", response_model=BulkResult, dependencies=[Depends(OPERATE)])
async def bulk(payload: BulkIn, db: AsyncSession = Depends(get_db), claims: dict = Depends(get_current_claims)):
    """Approves, or marks paid, many commissions at once. Each is handled on its
    own, so one that can't be processed never blocks the rest."""
    done, failed = 0, []
    for commission_id in payload.ids:
        try:
            if payload.action == "approve":
                await svc.approve_commission(db, commission_id, _user_id(claims))
            else:
                await svc.pay_commission(db, commission_id, _user_id(claims), payload.payout_reference or "", payload.payout_method)
            done += 1
        except HTTPException as exc:
            await db.rollback()
            failed.append({"id": str(commission_id), "error": exc.detail})
    return BulkResult(done=done, failed=failed)


# ----------------------------------------------------------------- summary


@router.get("/summary", response_model=SummaryOut, dependencies=[Depends(OPERATE)])
async def summary(db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            select(AffiliateCommission.status, func.count(), func.coalesce(func.sum(AffiliateCommission.commission_amount), 0))
            .group_by(AffiliateCommission.status)
        )
    ).all()
    by_status = {s: (int(n), Decimal(total)) for s, n, total in rows}
    zero = (0, Decimal("0"))
    referred = await db.scalar(select(func.count()).select_from(Referral).where(Referral.referred_customer_id.is_not(None))) or 0
    converted = await db.scalar(select(func.count()).select_from(Referral).where(Referral.status.in_(("converted", "rewarded")))) or 0
    affiliates = await db.scalar(select(func.count()).select_from(Affiliate)) or 0
    return SummaryOut(
        pending_count=by_status.get("pending", zero)[0], pending_amount=by_status.get("pending", zero)[1],
        approved_count=by_status.get("approved", zero)[0], approved_amount=by_status.get("approved", zero)[1],
        paid_count=by_status.get("paid", zero)[0], paid_amount=by_status.get("paid", zero)[1],
        affiliates=affiliates, referred=referred, converted=converted,
    )
