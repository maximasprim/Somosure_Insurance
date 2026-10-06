from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.phone import phone_variants
from app.models.crm import Communication, Lead, LeadActivity
from app.models.customer import Customer


async def submit_contact_message(
    db: AsyncSession, full_name: str, phone: str, email: str | None, message: str, product_interest: str | None = None
) -> dict:
    """Public contact form - no auth required, same guest-resolution
    pattern as the quote engine (app/services/quote_service.py): match or
    create a Customer by phone, then create/advance a Lead so the message
    lands in the sales pipeline rather than disappearing into an inbox
    nobody checks."""
    customer = await db.scalar(
        select(Customer).where(Customer.phone.in_(phone_variants(phone))).order_by(Customer.created_at.asc())
    )
    if not customer:
        customer = Customer(full_name=full_name, phone=phone, email=email, lead_source="website")
        db.add(customer)
        await db.flush()

    db.add(Communication(customer_id=customer.id, channel="in_app", direction="inbound", subject="Contact form", body=message))

    lead = await db.scalar(select(Lead).where(Lead.customer_id == customer.id, Lead.stage.notin_(["won", "lost"])))
    if not lead:
        lead = Lead(customer_id=customer.id, stage="new", source="website", product_interest=product_interest)
        db.add(lead)
        await db.flush()
    elif product_interest:
        # An agent-callback request for a product we can't quote online yet
        # (e.g. medical) - record what they wanted on the lead so the agent
        # who picks it up knows without reading the message.
        lead.product_interest = product_interest
    db.add(
        LeadActivity(
            lead_id=lead.id,
            activity_type="agent_callback_requested" if product_interest else "contact_form",
            notes=message,
        )
    )

    await db.commit()
    return {"received": True}
