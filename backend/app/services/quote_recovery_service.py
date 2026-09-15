from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.automation.engine import emit_event
from app.models.application import Application
from app.models.quote import Quote, QuoteRequest

ABANDONED_AFTER_HOURS = 4


async def scan_abandoned_quotes(db: AsyncSession) -> dict:
    """A quote request that got real quotes back but never became an
    application within ABANDONED_AFTER_HOURS is 'abandoned' (spec §40).
    Fires quote.abandoned once per quote request - enforced via the
    quote_requests.status flag itself rather than a separate event log,
    since a given quote request can only be abandoned once."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=ABANDONED_AFTER_HOURS)

    candidates = (
        await db.scalars(
            select(QuoteRequest).where(QuoteRequest.status == "quoted", QuoteRequest.created_at <= cutoff)
        )
    ).all()

    recovered = 0
    for qr in candidates:
        has_application = await db.scalar(
            select(Application)
            .join(Quote, Application.quote_id == Quote.id)
            .where(Quote.quote_request_id == qr.id)
        )
        if has_application:
            qr.status = "converted"
            continue

        if not qr.customer_id:
            qr.status = "expired"
            continue

        await emit_event(
            db,
            "quote.abandoned",
            entity_type="quote_request",
            entity_id=str(qr.id),
            context={"quote_reference": qr.reference, "customer_id": str(qr.customer_id), "category": qr.category},
        )
        qr.status = "abandoned"
        recovered += 1

    await db.commit()
    return {"checked": len(candidates), "recovery_reminders_sent": recovered}
