from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.payment import Payment
from app.models.policy import Policy

RENEWAL_WINDOW_DAYS = 60


async def get_dashboard(db: AsyncSession, customer_id: str) -> dict:
    active_policies = (
        await db.scalars(select(Policy).where(Policy.customer_id == customer_id, Policy.status == "active"))
    ).all()

    pending_applications = (
        await db.scalars(
            select(Application).where(
                Application.customer_id == customer_id,
                Application.status.in_(["draft", "documents_required", "submitted", "approved"]),
            )
        )
    ).all()

    renewal_cutoff = date.today() + timedelta(days=RENEWAL_WINDOW_DAYS)
    upcoming_renewals = (
        await db.scalars(
            select(Policy).where(
                Policy.customer_id == customer_id,
                Policy.status == "active",
                Policy.end_date <= renewal_cutoff,
            )
        )
    ).all()

    outstanding_payments = (
        await db.scalars(
            select(Payment).where(Payment.customer_id == customer_id, Payment.status.in_(["initiated", "pending", "failed"]))
        )
    ).all()

    return {
        "active_policies": active_policies,
        "pending_applications": pending_applications,
        "upcoming_renewals": upcoming_renewals,
        "outstanding_payments": outstanding_payments,
    }
