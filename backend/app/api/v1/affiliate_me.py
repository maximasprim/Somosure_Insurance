"""The signed-in customer's side of the affiliate program: their code(s),
referrals, earnings, and (if enrolled) payout number."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_customer
from app.models.affiliate import Affiliate, AffiliateCommission
from app.models.customer import Customer
from app.schemas.affiliate import MyAffiliateOut, MyAffiliateUpdate, MyCommissionOut
from app.services import affiliate_service as svc

router = APIRouter(prefix="/api/v1/me/affiliate", tags=["affiliate"])


async def _overview(db: AsyncSession, customer: Customer) -> MyAffiliateOut:
    settings = await svc.get_affiliate_settings(db)
    affiliate = await db.scalar(select(Affiliate).where(Affiliate.customer_id == customer.id))
    counts = await svc.referral_counts(db, customer.id)
    earned = await svc.earnings_by_status(db, customer.id)

    rows = (
        await db.scalars(
            select(AffiliateCommission)
            .where(AffiliateCommission.referrer_customer_id == customer.id)
            .order_by(AffiliateCommission.created_at.desc())
            .limit(20)
        )
    ).all()
    commissions = []
    for c in rows:
        referred = await db.get(Customer, c.referred_customer_id)
        first_name = (referred.full_name.split()[0] if referred and referred.full_name else None)  # first name only
        commissions.append(
            MyCommissionOut(
                id=c.id, category=c.category, referred_first_name=first_name, commission_amount=c.commission_amount,
                status=c.status, created_at=c.created_at, paid_at=c.paid_at,
            )
        )

    return MyAffiliateOut(
        program_enabled=settings.program_enabled,
        can_self_enroll=bool(settings.program_enabled and settings.allow_self_enrollment and not affiliate),
        is_affiliate=bool(affiliate),
        affiliate_code=affiliate.code if affiliate else None,
        affiliate_status=affiliate.status if affiliate else None,
        payout_phone=(affiliate.payout_phone if affiliate else None) or customer.phone,
        referred=counts["referred"],
        converted=counts["converted"],
        earned_pending=earned.get("pending", Decimal("0")),
        earned_approved=earned.get("approved", Decimal("0")),
        earned_paid=earned.get("paid", Decimal("0")),
        commissions=commissions,
    )


@router.get("", response_model=MyAffiliateOut)
async def my_affiliate(customer: Customer = Depends(get_current_customer), db: AsyncSession = Depends(get_db)):
    return await _overview(db, customer)


@router.post("/enroll", response_model=MyAffiliateOut)
async def enroll_me(customer: Customer = Depends(get_current_customer), db: AsyncSession = Depends(get_db)):
    settings = await svc.get_affiliate_settings(db)
    if not (settings.program_enabled and settings.allow_self_enrollment):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Joining the affiliate program is by invitation - please contact us.")
    await svc.enroll_affiliate(db, customer.id)
    return await _overview(db, customer)


@router.patch("", response_model=MyAffiliateOut)
async def update_my_payout(
    payload: MyAffiliateUpdate, customer: Customer = Depends(get_current_customer), db: AsyncSession = Depends(get_db)
):
    affiliate = await db.scalar(select(Affiliate).where(Affiliate.customer_id == customer.id))
    if not affiliate:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "You're not an affiliate yet.")
    affiliate.payout_phone = payload.payout_phone.strip()
    await db.commit()
    return await _overview(db, customer)
