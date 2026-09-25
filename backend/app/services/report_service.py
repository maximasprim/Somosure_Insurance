from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.claim import Claim
from app.models.crm import Lead
from app.models.customer import Customer
from app.models.payment import Payment
from app.models.policy import Policy
from app.models.provider import InsuranceProvider
from app.models.quote import Quote, QuoteRequest
from app.models.renewal import Renewal
from app.models.sticker import Sticker


async def get_overview(db: AsyncSession) -> dict:
    now = datetime.now(timezone.utc)
    month_start = date(now.year, now.month, 1)

    total_customers = await db.scalar(select(func.count(Customer.id))) or 0
    new_customers = await db.scalar(select(func.count(Customer.id)).where(Customer.created_at >= month_start)) or 0

    total_leads = await db.scalar(select(func.count(Lead.id))) or 0
    won_leads = await db.scalar(select(func.count(Lead.id)).where(Lead.stage == "won")) or 0

    total_quote_requests = await db.scalar(select(func.count(QuoteRequest.id))) or 0
    total_quotes = await db.scalar(select(func.count(Quote.id))) or 0

    total_policies = await db.scalar(select(func.count(Policy.id))) or 0
    active_policies = await db.scalar(select(func.count(Policy.id)).where(Policy.status == "active")) or 0
    total_premium = await db.scalar(select(func.coalesce(func.sum(Policy.premium), 0)).where(Policy.status == "active")) or Decimal(0)
    total_commission = await db.scalar(select(func.coalesce(func.sum(Policy.commission), 0))) or Decimal(0)

    successful_revenue = await db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.status == "successful")
    ) or Decimal(0)
    outstanding_payments = await db.scalar(
        select(func.count(Payment.id)).where(Payment.status.in_(["initiated", "pending", "failed"]))
    ) or 0

    renewals_due = await db.scalar(select(func.count(Renewal.id)).where(Renewal.status == "due")) or 0
    renewals_renewed = await db.scalar(select(func.count(Renewal.id)).where(Renewal.status == "renewed")) or 0

    sticker_rows = (await db.execute(select(Sticker.status, func.count(Sticker.id)).group_by(Sticker.status))).all()

    claim_rows = (await db.execute(select(Claim.status, func.count(Claim.id)).group_by(Claim.status))).all()
    claims_by_status = {status: count for status, count in claim_rows}
    total_claims = sum(claims_by_status.values())
    open_claims = total_claims - sum(
        claims_by_status.get(s, 0) for s in ("settled", "closed", "rejected")
    )

    # Quote-to-policy conversion: policies issued ÷ quote requests that
    # actually received quotes back. A crude but honest proxy - the
    # platform doesn't yet track which specific quote became which policy
    # request-for-request, only application→policy (see policy_service).
    quoted_requests = await db.scalar(select(func.count(QuoteRequest.id)).where(QuoteRequest.status.in_(["quoted", "converted"]))) or 0
    conversion_rate = round((total_policies / quoted_requests) * 100, 1) if quoted_requests else None

    return {
        "customers": {"total": total_customers, "new_this_month": new_customers},
        "leads": {"total": total_leads, "won": won_leads},
        "quotes": {"requests": total_quote_requests, "quotes_returned": total_quotes, "conversion_rate_pct": conversion_rate},
        "policies": {"total": total_policies, "active": active_policies, "total_active_premium": total_premium},
        "revenue": {"collected": successful_revenue, "commission": total_commission, "outstanding_payment_count": outstanding_payments},
        "renewals": {"due": renewals_due, "renewed": renewals_renewed},
        "stickers_by_status": {status: count for status, count in sticker_rows},
        "claims": {"total": total_claims, "open": open_claims, "by_status": claims_by_status},
    }


async def get_provider_performance(db: AsyncSession) -> list[dict]:
    """Quotes returned and policies issued per provider row. An aggregator
    row's count reflects every underlying-insurer quote it fanned out
    (see docs/PROVIDER_ADAPTERS.md's aggregator architecture section), not
    just one - which is the honest picture of what that integration is
    actually contributing."""
    providers = (await db.scalars(select(InsuranceProvider))).all()
    results = []
    for provider in providers:
        quote_count = await db.scalar(select(func.count(Quote.id)).where(Quote.provider_id == provider.id)) or 0
        policy_count = await db.scalar(select(func.count(Policy.id)).where(Policy.provider_id == provider.id)) or 0
        results.append(
            {
                "provider_id": str(provider.id),
                "name": provider.name,
                "provider_type": provider.provider_type,
                "status": provider.status,
                "quotes_returned": quote_count,
                "policies_issued": policy_count,
            }
        )
    return results
