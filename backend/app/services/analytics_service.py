"""Numbers behind the admin "Reports & analytics" dashboard.

One call returns everything the page draws: headline figures compared with the
previous period, a trend over time, the sales funnel and a set of breakdowns
(by category, provider, status, source...). It is separate from
report_service.py, which keeps serving the older /overview and
/provider-performance endpoints exactly as before.

Design notes:
  * Everything is read-only.
  * Each section is computed on its own and guarded (see _safe): if one query
    ever fails - say a table is missing in some environment - that section comes
    back empty and is named in "unavailable", instead of the whole dashboard
    returning an error.
  * Times are bucketed in UTC. A payment made late in the evening in Nairobi
    (UTC+3) can fall on the next day's bucket; for trends over days, weeks and
    months that is an acceptable simplification.
  * Money is returned as plain numbers (KES) ready to chart.
"""

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Awaitable, Callable

from sqlalchemy import func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.affiliate import AffiliateCommission
from app.models.application import Application
from app.models.claim import Claim
from app.models.crm import Lead
from app.models.customer import Customer
from app.models.financing import FinancingAgreement, FinancingApplication, FinancingInstallment
from app.models.payment import Payment
from app.models.policy import Policy
from app.models.provider import InsuranceProvider
from app.models.quote import Quote, QuoteRequest
from app.models.referral import Referral
from app.models.renewal import Renewal
from app.models.sticker import Sticker
from app.services.analytics_buckets import bucket_dates, bucket_unit, merge_trend, pct_change

logger = logging.getLogger("somosure.analytics")

# Application statuses that mean "has been sent to underwriting" / "was approved".
SUBMITTED_OR_BEYOND = ("under_review", "submitted", "approved", "payment_pending", "rejected")
APPROVED = ("approved", "payment_pending")
CLAIM_CLOSED = ("settled", "closed", "rejected")
STICKER_IN_PROGRESS = ("pending", "validated", "payment_confirmed", "generating")

LEAD_STAGE_ORDER = ["new", "contacted", "qualified", "quote", "negotiation", "won", "lost"]
APPLICATION_STATUS_ORDER = ["draft", "documents_required", "submitted", "under_review", "approved", "payment_pending", "rejected"]
CLAIM_STATUS_ORDER = ["reported", "documents_required", "submitted", "under_review", "insurer_review", "approved", "rejected", "settled", "closed"]
FINANCING_STATUS_ORDER = ["eligibility_checked", "submitted", "approved", "rejected", "cancelled"]
RENEWAL_STATUS_ORDER = ["due", "contacted", "quoted", "paid", "renewed", "lost"]


def _f(value: Any) -> float:
    return float(value or 0)


async def _safe(db: AsyncSession, name: str, unavailable: list[str], default: Any, work: Callable[[], Awaitable[Any]]) -> Any:
    """Runs one section; on any failure logs it, clears the failed transaction
    so later sections can still run, and returns `default`."""
    try:
        return await work()
    except Exception:
        logger.exception("Analytics section '%s' failed", name)
        try:
            await db.rollback()
        except Exception:
            pass
        unavailable.append(name)
        return default


def _ordered(rows: list[dict], order: list[str]) -> list[dict]:
    """Known statuses in their natural order first, anything unexpected after."""
    rank = {name: i for i, name in enumerate(order)}
    return sorted(rows, key=lambda r: (rank.get(r["name"], len(order)), -r["count"]))


async def _count(db: AsyncSession, column: Any, *where: Any) -> int:
    return int(await db.scalar(select(func.count(column)).where(*where)) or 0)


async def _sum(db: AsyncSession, column: Any, *where: Any) -> float:
    return _f(await db.scalar(select(func.coalesce(func.sum(column), 0)).where(*where)))


async def _grouped(db: AsyncSession, key_column: Any, *where: Any, amount: Any = None) -> list[dict]:
    """{name, count[, amount]} per distinct value of `key_column`, biggest first."""
    columns = [key_column, func.count()]
    if amount is not None:
        columns.append(func.coalesce(func.sum(amount), 0))
    rows = (await db.execute(select(*columns).where(*where).group_by(key_column))).all()
    out = []
    for row in rows:
        item: dict[str, Any] = {"name": row[0] if row[0] is not None else "unknown", "count": int(row[1])}
        if amount is not None:
            item["amount"] = _f(row[2])
        out.append(item)
    out.sort(key=lambda r: r["count"], reverse=True)
    return out


def _bucket_expr(column: Any, unit: str) -> Any:
    # `unit` comes from bucket_unit() (day/week/month) and 'UTC' is fixed, so
    # both are written into the SQL text rather than sent as parameters -
    # otherwise Postgres sees the SELECT and GROUP BY expressions as different.
    return func.date_trunc(literal_column(f"'{unit}'"), func.timezone(literal_column("'UTC'"), column))


async def _series(db: AsyncSession, timestamp: Any, unit: str, start: datetime, *where: Any, value: Any = None) -> dict[date, float]:
    """Count (or sum of `value`) per time bucket since `start`."""
    expr = _bucket_expr(timestamp, unit)
    aggregate = func.count() if value is None else func.coalesce(func.sum(value), 0)
    stmt = (
        select(expr.label("bucket"), aggregate.label("total"))
        .where(timestamp >= start, *where)
        .group_by(expr)
        .order_by(expr)
    )
    out: dict[date, float] = {}
    for bucket, total in (await db.execute(stmt)).all():
        key = bucket.date() if isinstance(bucket, datetime) else bucket
        out[key] = _f(total) if value is not None else int(total)
    return out


async def _window_totals(db: AsyncSession, start: datetime, end: datetime) -> dict[str, float]:
    """The headline figures for one window [start, end)."""
    revenue = await _sum(db, Payment.amount, Payment.status == "successful", Payment.created_at >= start, Payment.created_at < end)
    premium = await _sum(db, Policy.premium, Policy.created_at >= start, Policy.created_at < end)
    commission = await _sum(db, Policy.commission, Policy.created_at >= start, Policy.created_at < end)
    policies = await _count(db, Policy.id, Policy.created_at >= start, Policy.created_at < end)
    quote_requests = await _count(db, QuoteRequest.id, QuoteRequest.created_at >= start, QuoteRequest.created_at < end)
    customers = await _count(db, Customer.id, Customer.created_at >= start, Customer.created_at < end)
    applications = await _count(db, Application.id, Application.created_at >= start, Application.created_at < end)
    return {
        "revenue": revenue,
        "premium_written": premium,
        "commission": commission,
        "policies_issued": float(policies),
        "quote_requests": float(quote_requests),
        "new_customers": float(customers),
        "applications": float(applications),
        "conversion_pct": round(policies / quote_requests * 100, 1) if quote_requests else 0.0,
    }


def _kpis(current: dict[str, float], previous: dict[str, float]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for name, value in current.items():
        before = previous.get(name, 0.0)
        item: dict[str, Any] = {"value": value, "previous": before, "change_pct": pct_change(value, before)}
        if name == "conversion_pct":
            # A rate is better compared in percentage points than as a percentage of a percentage.
            item["change_pts"] = round(value - before, 1)
        out[name] = item
    return out


async def get_analytics(db: AsyncSession, days: int) -> dict:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    previous_start = start - timedelta(days=days)
    end = now + timedelta(minutes=1)  # include rows created this very second
    unit = bucket_unit(days)
    unavailable: list[str] = []

    async def safe(name: str, default: Any, work: Callable[[], Awaitable[Any]]) -> Any:
        return await _safe(db, name, unavailable, default, work)

    # --- headline figures, this period vs the one before it
    kpis = await safe(
        "kpis",
        {},
        lambda: _kpi_section(db, start, previous_start, end),
    )

    # --- point-in-time counts (not tied to the chosen period)
    snapshot = await safe("snapshot", {}, lambda: _snapshot_section(db, start))

    # --- trend over time
    trend = await safe("trend", [], lambda: _trend_section(db, start, now, unit))

    # --- sales funnel
    funnel = await safe("funnel", [], lambda: _funnel_section(db, start))

    # --- breakdowns
    quotes_by_category = await safe("quotes_by_category", [], lambda: _grouped(db, QuoteRequest.category, QuoteRequest.created_at >= start))
    premium_by_category = await safe("premium_by_category", [], lambda: _premium_by_category(db, start))
    providers = await safe("providers", [], lambda: _providers_section(db, start))
    policies_by_source = await safe(
        "policies_by_source", [], lambda: _grouped(db, Policy.source, Policy.created_at >= start, amount=Policy.premium)
    )
    payments_by_status = await safe(
        "payments_by_status", [], lambda: _grouped(db, Payment.status, Payment.created_at >= start, amount=Payment.amount)
    )
    payments_by_method = await safe(
        "payments_by_method",
        [],
        lambda: _grouped(db, Payment.method, Payment.created_at >= start, Payment.status == "successful", amount=Payment.amount),
    )
    applications_by_status = await safe(
        "applications_by_status",
        [],
        lambda: _ordered_group(db, Application.status, APPLICATION_STATUS_ORDER, Application.created_at >= start),
    )
    claims_by_status = await safe(
        "claims_by_status", [], lambda: _ordered_group(db, Claim.status, CLAIM_STATUS_ORDER, Claim.created_at >= start)
    )
    leads_by_stage = await safe("leads_by_stage", [], lambda: _ordered_group(db, Lead.stage, LEAD_STAGE_ORDER, Lead.created_at >= start))
    leads_by_source = await safe("leads_by_source", [], lambda: _grouped(db, Lead.source, Lead.created_at >= start))
    financing_by_status = await safe(
        "financing_by_status",
        [],
        lambda: _ordered_group(
            db, FinancingApplication.status, FINANCING_STATUS_ORDER, FinancingApplication.created_at >= start,
            amount=FinancingApplication.financed_amount,
        ),
    )
    agreements_by_status = await safe(
        "agreements_by_status",
        [],
        lambda: _grouped(db, FinancingAgreement.status, FinancingAgreement.id.is_not(None), amount=FinancingAgreement.financed_amount),
    )
    renewals_by_status = await safe(
        "renewals_by_status", [], lambda: _ordered_group(db, Renewal.status, RENEWAL_STATUS_ORDER, Renewal.id.is_not(None))
    )
    stickers_by_status = await safe("stickers_by_status", [], lambda: _grouped(db, Sticker.status, Sticker.id.is_not(None)))
    commissions_by_status = await safe(
        "commissions_by_status",
        [],
        lambda: _grouped(
            db, AffiliateCommission.status, AffiliateCommission.created_at >= start, amount=AffiliateCommission.commission_amount
        ),
    )
    referrals_by_status = await safe("referrals_by_status", [], lambda: _grouped(db, Referral.status, Referral.created_at >= start))

    return {
        "range_days": days,
        "bucket": unit,
        "generated_at": now.isoformat(),
        "period": {"start": start.isoformat(), "end": now.isoformat()},
        "kpis": kpis,
        "snapshot": snapshot,
        "trend": trend,
        "funnel": funnel,
        "quotes_by_category": quotes_by_category,
        "premium_by_category": premium_by_category,
        "providers": providers,
        "policies_by_source": policies_by_source,
        "payments_by_status": payments_by_status,
        "payments_by_method": payments_by_method,
        "applications_by_status": applications_by_status,
        "claims_by_status": claims_by_status,
        "leads_by_stage": leads_by_stage,
        "leads_by_source": leads_by_source,
        "financing_by_status": financing_by_status,
        "agreements_by_status": agreements_by_status,
        "renewals_by_status": renewals_by_status,
        "stickers_by_status": stickers_by_status,
        "commissions_by_status": commissions_by_status,
        "referrals_by_status": referrals_by_status,
        "unavailable": unavailable,
    }


# --- sections ---------------------------------------------------------------


async def _ordered_group(db: AsyncSession, key_column: Any, order: list[str], *where: Any, amount: Any = None) -> list[dict]:
    return _ordered(await _grouped(db, key_column, *where, amount=amount), order)


async def _kpi_section(db: AsyncSession, start: datetime, previous_start: datetime, end: datetime) -> dict:
    current = await _window_totals(db, start, end)
    previous = await _window_totals(db, previous_start, start)
    return _kpis(current, previous)


async def _snapshot_section(db: AsyncSession, start: datetime) -> dict:
    today = date.today()
    return {
        "active_policies": await _count(db, Policy.id, Policy.status == "active"),
        "demo_policies_in_period": await _count(db, Policy.id, Policy.is_mock.is_(True), Policy.created_at >= start),
        "expiring_30d": await _count(
            db, Policy.id, Policy.status == "active", Policy.end_date >= today, Policy.end_date <= today + timedelta(days=30)
        ),
        "renewals_due": await _count(db, Renewal.id, Renewal.status == "due"),
        "applications_awaiting_review": await _count(db, Application.id, Application.status == "submitted"),
        "open_claims": await _count(db, Claim.id, Claim.status.notin_(CLAIM_CLOSED)),
        "financing_awaiting_decision": await _count(db, FinancingApplication.id, FinancingApplication.status == "submitted"),
        "overdue_installments": await _count(db, FinancingInstallment.id, FinancingInstallment.status == "overdue"),
        "pending_payments": await _count(db, Payment.id, Payment.status.in_(["initiated", "pending"])),
        "stickers_in_progress": await _count(db, Sticker.id, Sticker.status.in_(STICKER_IN_PROGRESS)),
    }


async def _trend_section(db: AsyncSession, start: datetime, now: datetime, unit: str) -> list[dict]:
    revenue = await _series(db, Payment.created_at, unit, start, Payment.status == "successful", value=Payment.amount)
    premium = await _series(db, Policy.created_at, unit, start, value=Policy.premium)
    policies = await _series(db, Policy.created_at, unit, start)
    quote_requests = await _series(db, QuoteRequest.created_at, unit, start)
    applications = await _series(db, Application.created_at, unit, start)
    customers = await _series(db, Customer.created_at, unit, start)
    claims = await _series(db, Claim.created_at, unit, start)
    dates = bucket_dates(start.date(), now.date(), unit)
    return merge_trend(
        dates,
        {
            "revenue": revenue,
            "premium": premium,
            "policies": policies,
            "quote_requests": quote_requests,
            "applications": applications,
            "customers": customers,
            "claims": claims,
        },
    )


async def _funnel_section(db: AsyncSession, start: datetime) -> list[dict]:
    return [
        {"name": "Quote requests", "value": await _count(db, QuoteRequest.id, QuoteRequest.created_at >= start)},
        {"name": "Applications started", "value": await _count(db, Application.id, Application.created_at >= start)},
        {
            "name": "Sent to underwriting",
            "value": await _count(db, Application.id, Application.created_at >= start, Application.status.in_(SUBMITTED_OR_BEYOND)),
        },
        {
            "name": "Approved",
            "value": await _count(db, Application.id, Application.created_at >= start, Application.status.in_(APPROVED)),
        },
        {"name": "Policies issued", "value": await _count(db, Policy.id, Policy.created_at >= start)},
    ]


async def _premium_by_category(db: AsyncSession, start: datetime) -> list[dict]:
    """Policies and premium per product category, found by walking
    policy -> application -> quote -> quote request (where the category lives)."""
    stmt = (
        select(QuoteRequest.category, func.count(Policy.id), func.coalesce(func.sum(Policy.premium), 0))
        .select_from(Policy)
        .join(Application, Application.id == Policy.application_id)
        .join(Quote, Quote.id == Application.quote_id)
        .join(QuoteRequest, QuoteRequest.id == Quote.quote_request_id)
        .where(Policy.created_at >= start)
        .group_by(QuoteRequest.category)
    )
    rows = (await db.execute(stmt)).all()
    out = [{"name": r[0] or "unknown", "count": int(r[1]), "amount": _f(r[2])} for r in rows]
    out.sort(key=lambda r: r["amount"], reverse=True)
    return out


async def _providers_section(db: AsyncSession, start: datetime) -> list[dict]:
    quote_rows = (
        await db.execute(select(Quote.provider_id, func.count(Quote.id)).where(Quote.created_at >= start).group_by(Quote.provider_id))
    ).all()
    policy_rows = (
        await db.execute(
            select(Policy.provider_id, func.count(Policy.id), func.coalesce(func.sum(Policy.premium), 0))
            .where(Policy.created_at >= start)
            .group_by(Policy.provider_id)
        )
    ).all()
    names = {p.id: p.name for p in (await db.scalars(select(InsuranceProvider))).all()}

    merged: dict[Any, dict] = {}
    for provider_id, count in quote_rows:
        merged.setdefault(provider_id, {"quotes": 0, "policies": 0, "premium": 0.0})["quotes"] = int(count)
    for provider_id, count, premium in policy_rows:
        row = merged.setdefault(provider_id, {"quotes": 0, "policies": 0, "premium": 0.0})
        row["policies"] = int(count)
        row["premium"] = _f(premium)

    out = [{"name": names.get(pid, "Unknown provider"), **values} for pid, values in merged.items()]
    out.sort(key=lambda r: (r["premium"], r["quotes"]), reverse=True)
    return out[:8]
