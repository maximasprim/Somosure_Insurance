from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.claim import Claim
from app.models.customer import Customer
from app.models.payment import Payment
from app.models.policy import Policy
from app.models.quote import QuoteRequest
from app.models.sales_ledger import SalesEntry


async def global_search(db: AsyncSession, query: str, limit: int = 10) -> dict:
    """Spec §28: search customers, quotes, policies, claims, applications,
    payments, documents, vehicles. Documents and vehicles are omitted here
    - they're rarely searched by free text on their own fields (a document
    is found via its parent application/claim, a vehicle via its owner) -
    everything else searches its natural identifying fields.
    """
    like = f"%{query}%"

    customers = (
        await db.scalars(
            select(Customer)
            .where(or_(Customer.full_name.ilike(like), Customer.phone.ilike(like), Customer.email.ilike(like)))
            .limit(limit)
        )
    ).all()

    quote_requests = (
        await db.scalars(select(QuoteRequest).where(QuoteRequest.reference.ilike(like)).limit(limit))
    ).all()

    policies = (
        await db.scalars(select(Policy).where(Policy.policy_number.ilike(like)).limit(limit))
    ).all()

    claims = (
        await db.scalars(select(Claim).where(Claim.reference.ilike(like)).limit(limit))
    ).all()

    applications = (
        await db.scalars(select(Application).where(Application.reference.ilike(like)).limit(limit))
    ).all()

    payments = (
        await db.scalars(select(Payment).where(Payment.reference.ilike(like)).limit(limit))
    ).all()

    # Policies recorded in the weekly report workbook. Guarded so search keeps working if those tables are not there yet.
    try:
        workbook_rows = (
            await db.scalars(
                select(SalesEntry)
                .where(
                    SalesEntry.status == "active",
                    or_(SalesEntry.client_name.ilike(like), SalesEntry.policy_number.ilike(like), SalesEntry.reg_no.ilike(like), SalesEntry.phone.ilike(like)),
                )
                .order_by(SalesEntry.expiry_date.desc().nulls_last())
                .limit(limit)
            )
        ).all()
    except Exception:
        await db.rollback()
        workbook_rows = []

    return {
        "workbook": [
            {
                "id": str(w.id), "client_name": w.client_name, "policy_number": w.policy_number, "reg_no": w.reg_no or w.asset_ref,
                "underwriter": w.underwriter, "expiry_date": w.expiry_date.isoformat() if w.expiry_date else None,
                "customer_id": str(w.customer_id) if w.customer_id else None,
            }
            for w in workbook_rows
        ],
        "customers": [{"id": str(c.id), "full_name": c.full_name, "phone": c.phone, "email": c.email} for c in customers],
        "quotes": [{"id": str(q.id), "reference": q.reference, "category": q.category, "status": q.status} for q in quote_requests],
        "policies": [{"id": str(p.id), "policy_number": p.policy_number, "status": p.status} for p in policies],
        "claims": [{"id": str(c.id), "reference": c.reference, "status": c.status} for c in claims],
        "applications": [{"id": str(a.id), "reference": a.reference, "status": a.status} for a in applications],
        "payments": [{"id": str(p.id), "reference": p.reference, "status": p.status} for p in payments],
    }
