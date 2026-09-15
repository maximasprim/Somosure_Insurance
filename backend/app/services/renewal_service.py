from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.automation.engine import emit_event
from app.models.policy import Policy
from app.models.renewal import REMINDER_DAYS_BEFORE_EXPIRY, Renewal, RenewalEvent


async def scan_renewals(db: AsyncSession) -> dict:
    """Finds active policies inside the reminder window (spec §16: 60/30/
    14/7/3/1/0 days before expiry) and fires exactly one reminder per
    policy per day-bucket - idempotent by checking RenewalEvent for that
    bucket before creating another. Meant to be run daily by a scheduled
    job (Phase 10 infra); the admin endpoint runs it on demand until then.
    """
    today = date.today()
    reminders_sent = 0

    active_policies = (await db.scalars(select(Policy).where(Policy.status == "active"))).all()

    for policy in active_policies:
        days_remaining = (policy.end_date - today).days
        if days_remaining not in REMINDER_DAYS_BEFORE_EXPIRY:
            continue

        renewal = await db.scalar(select(Renewal).where(Renewal.policy_id == policy.id))
        if not renewal:
            renewal = Renewal(policy_id=policy.id, due_date=policy.end_date, status="due")
            db.add(renewal)
            await db.flush()

        already_sent = await db.scalar(
            select(RenewalEvent).where(
                RenewalEvent.renewal_id == renewal.id,
                RenewalEvent.event_type == "reminder_sent",
                RenewalEvent.days_before_expiry == days_remaining,
            )
        )
        if already_sent:
            continue

        db.add(
            RenewalEvent(
                renewal_id=renewal.id,
                event_type="reminder_sent",
                days_before_expiry=days_remaining,
                notes=f"{days_remaining} days before expiry",
            )
        )
        await emit_event(
            db,
            "renewal.reminder_due",
            entity_type="policy",
            entity_id=str(policy.id),
            context={
                "policy_id": str(policy.id),
                "policy_number": policy.policy_number,
                "customer_id": str(policy.customer_id),
                "days_remaining": days_remaining,
            },
        )
        reminders_sent += 1

    await db.commit()
    return {"policies_checked": len(active_policies), "reminders_sent": reminders_sent}
