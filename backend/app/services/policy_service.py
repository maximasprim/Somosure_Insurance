from datetime import date, timedelta

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.automation.engine import emit_event
from app.models.application import Application
from app.models.policy import Policy, PolicyEvent
from app.models.provider import InsuranceProvider
from app.models.quote import Quote, QuoteRequest
from app.providers.registry import get_adapter


async def issue_policy(db: AsyncSession, application_id: str) -> Policy:
    application = await db.get(Application, application_id)
    if not application:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    if application.status not in ("submitted", "approved"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Application must be submitted and approved before issuance")

    quote = await db.get(Quote, application.quote_id)
    provider = await db.get(InsuranceProvider, quote.provider_id)
    adapter = get_adapter(provider)
    quote_request = await db.get(QuoteRequest, quote.quote_request_id)

    result = await adapter.issue_policy(application.provider_reference or application.reference)

    policy = Policy(
        policy_number=result.policy_number,
        application_id=application.id,
        provider_id=provider.id,
        product_id=quote.product_id,
        customer_id=application.customer_id,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=365),
        premium=quote.premium,
        payment_status="pending",
        status="active" if result.status == "active" else "under_review",
        source="website",
        is_mock=result.is_mock,
    )
    db.add(policy)
    await db.flush()

    db.add(
        PolicyEvent(
            policy_id=policy.id,
            event_type="status_changed",
            from_status=None,
            to_status=policy.status,
            metadata_json={"provider_reference": result.policy_number, "is_mock": result.is_mock},
        )
    )

    application.status = "approved"

    if policy.status == "active":
        # Fires the seeded "generate sticker on motor policy activation"
        # and "notify customer" rules - see app/db/seed.py. Nothing here
        # hardcodes what happens next; that's entirely rule-driven.
        await emit_event(
            db,
            "policy.activated",
            entity_type="policy",
            entity_id=str(policy.id),
            context={
                "policy_id": str(policy.id),
                "policy_number": policy.policy_number,
                "customer_id": str(policy.customer_id),
                "category": quote_request.category if quote_request else None,
            },
        )

    await db.commit()
    await db.refresh(policy)

    from app.services.referral_service import mark_converted_if_referred

    await mark_converted_if_referred(db, str(policy.customer_id), str(policy.id))

    return policy
