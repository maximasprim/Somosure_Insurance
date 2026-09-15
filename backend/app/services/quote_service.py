import asyncio
import logging
import random
import string
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crm import Lead, LeadActivity
from app.models.customer import Customer
from app.models.provider import InsuranceProvider
from app.models.quote import Quote, QuoteRequest
from app.providers.registry import get_adapter

logger = logging.getLogger("somosure.quote_service")


def generate_reference() -> str:
    year = date.today().year
    suffix = "".join(random.choices(string.digits, k=6))
    return f"SOM-{year}-{suffix}"


async def resolve_customer(db: AsyncSession, customer_id: str | None, answers: dict) -> Customer | None:
    """Resolves the customer behind a quote request.

    - If customer_id is supplied and exists (a logged-in customer), use it.
    - Otherwise, try to match or create a guest Customer from whatever
      contact details the quote form collected (e.g. motor's owner_phone /
      owner_name) - this is what lets a guest quote become a real lead
      (spec §8: guest flow shouldn't mean "no record at all").
    - If neither is available, returns None and the quote proceeds
      anonymous (no lead is created for it).
    """
    if customer_id:
        existing = await db.get(Customer, customer_id)
        if existing:
            return existing

    phone = answers.get("owner_phone") or answers.get("phone")
    name = answers.get("owner_name") or answers.get("full_name")
    if not phone:
        return None

    guest = await db.scalar(select(Customer).where(Customer.phone == phone))
    if guest:
        return guest

    guest = Customer(full_name=name or "Guest", phone=phone, lead_source="website")
    db.add(guest)
    await db.flush()
    return guest


async def record_lead(db: AsyncSession, customer: Customer, category: str, quote_request_id) -> None:
    """Creates or advances a lead for this customer - every quote request
    should land somewhere an agent can follow up (spec §19: 'a new lead
    notification' should fire off nearly everything the customer does)."""
    lead = await db.scalar(select(Lead).where(Lead.customer_id == customer.id, Lead.stage.notin_(["won", "lost"])))
    if lead:
        lead.stage = "quote" if lead.stage in ("new", "contacted", "qualified") else lead.stage
        lead.product_interest = category
        lead.quote_request_id = quote_request_id
        activity_type = "quote_requested"
    else:
        lead = Lead(
            customer_id=customer.id,
            stage="quote",
            source=customer.lead_source or "website",
            product_interest=category,
            quote_request_id=quote_request_id,
        )
        db.add(lead)
        await db.flush()
        activity_type = "lead_created"

    db.add(LeadActivity(lead_id=lead.id, activity_type=activity_type, notes=f"Requested a {category} quote"))


async def request_quotes(
    db: AsyncSession, category: str, answers: dict, customer_id: str | None
) -> tuple[QuoteRequest, list[Quote], bool]:
    """Fan out a quote request to every active provider. If some providers
    fail, return the successful ones and flag partial failure - never break
    the whole comparison because one insurer's API is down (spec §46)."""

    customer = await resolve_customer(db, customer_id, answers)

    quote_request = QuoteRequest(
        reference=generate_reference(),
        customer_id=customer.id if customer else None,
        category=category,
        input_data=answers,
        status="routed",
    )
    db.add(quote_request)
    await db.flush()

    if customer:
        await record_lead(db, customer, category, quote_request.id)

    providers = (
        await db.scalars(select(InsuranceProvider).where(InsuranceProvider.status == "active"))
    ).all()

    any_failure = False

    async def _fetch(provider: InsuranceProvider):
        nonlocal any_failure
        adapter = get_adapter(provider)
        try:
            # get_quotes_bulk() is called for EVERY provider, aggregator or
            # not - direct insurer adapters inherit a default that just
            # wraps get_quote() in a single-item list, so this one call
            # handles both cases without branching here. An aggregator
            # returning quotes from several underlying insurers naturally
            # produces several Quote rows from one provider row.
            normalized_quotes = await adapter.get_quotes_bulk(category, answers)
        except Exception:
            logger.exception("Provider %s failed to return a quote", provider.name)
            any_failure = True
            return []

        created = []
        for normalized in normalized_quotes:
            quote = Quote(
                quote_request_id=quote_request.id,
                provider_id=provider.id,
                premium=normalized.premium,
                taxes=normalized.taxes,
                fees=normalized.fees,
                total=normalized.total,
                currency=normalized.currency,
                coverage=normalized.coverage,
                exclusions=normalized.exclusions,
                deductibles=normalized.deductibles,
                payment_options=normalized.payment_options,
                provider_metadata=normalized.metadata,
                underlying_provider_name=normalized.underlying_provider_name,
                is_mock=normalized.is_mock,
                valid_until=normalized.valid_until,
            )
            db.add(quote)
            created.append(quote)
        return created

    results = await asyncio.gather(*[_fetch(p) for p in providers])
    quotes = [q for batch in results for q in batch]

    quote_request.status = "quoted" if quotes else "partial_failure"
    await db.commit()
    await db.refresh(quote_request)
    for q in quotes:
        await db.refresh(q)

    return quote_request, quotes, any_failure
