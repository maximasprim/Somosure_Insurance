"""Adapter for a provider whose pricing comes from a configured rate card
(app/models/rate_card.py) rather than a live API - today, AMACO and
Pioneer Insurance Kenya (see app/db/rate_card_seed_data.py and
docs/RATE_CARDS.md).

get_quote() computes a real premium from real, sourced rates - is_mock is
False, unlike MockProvider - but this insurer has not given us a live API
to bind cover, submit documents, or take payment against, so every stage
after the quote is handled the same honest way the rest of this codebase
handles "no live API yet": marked for manual staff follow-up rather than
auto-approved, exactly like the claims staff-assisted fallback
(app/services/claim_service.py) for a provider with no claims API.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.rate_card import RateCardVehicleClass
from app.providers.base import (
    ApplicationResult,
    ClaimStatusResult,
    InsuranceProviderAdapter,
    NormalizedQuote,
    PolicyResult,
)
from app.services.rate_card_engine import RateCardNotConfigured, compute_motor_premium


class RateCardAdapter(InsuranceProviderAdapter):
    is_mock = False  # premiums are computed from a real, sourced rate card

    def __init__(self, provider_id: str):
        self.provider_id = provider_id

    async def get_products(self) -> list[dict[str, Any]]:
        async with AsyncSessionLocal() as db:
            classes = (
                await db.scalars(
                    select(RateCardVehicleClass).where(
                        RateCardVehicleClass.provider_id == self.provider_id,
                        RateCardVehicleClass.is_active.is_(True),
                    )
                )
            ).all()
            return [
                {
                    "category": c.product_category,
                    "name": c.label,
                    "code": c.code,
                    "data_confidence": c.data_confidence,
                }
                for c in classes
            ]

    async def get_quote(self, product_category: str, answers: dict[str, Any]) -> NormalizedQuote:
        if product_category != "motor":
            raise RateCardNotConfigured(
                f"This provider's rate card only covers motor products so far - no '{product_category}' "
                "rates have been supplied yet. Add them via /api/v1/admin/rate-cards."
            )

        async with AsyncSessionLocal() as db:
            breakdown = await compute_motor_premium(db, self.provider_id, answers)

        coverage = {
            "summary": f"{breakdown.vehicle_class_label} - {breakdown.cover_type.upper()} cover",
            "extensions": breakdown.extensions,
        }
        if breakdown.assumptions:
            coverage["assumptions"] = breakdown.assumptions
        if breakdown.data_confidence != "verified":
            coverage["data_confidence_notice"] = (
                "This rate is transcribed from a source document that did not parse cleanly and has not yet "
                "been verified against the original rate card - confirm before binding a real policy."
            )

        return NormalizedQuote(
            provider_id=self.provider_id,
            product_category=product_category,
            premium=breakdown.base_premium + breakdown.extensions_total,
            taxes=breakdown.phcf + breakdown.training_levy,
            fees=breakdown.stamp_duty,
            total=breakdown.total,
            coverage=coverage,
            exclusions={"items": ["Wear and tear", "Consequential loss", "Driving under the influence"]},
            deductibles={"excesses": breakdown.excesses} if breakdown.excesses else {},
            payment_options={"methods": ["mpesa", "card", "bank_transfer"], "installments_allowed": True},
            metadata={
                "quote_basis": "published_rate_card",
                "source_document": breakdown.source_document,
                "data_confidence": breakdown.data_confidence,
            },
            valid_until=datetime.now(timezone.utc) + timedelta(days=14),
            is_mock=False,
        )

    async def create_application(self, quote_ref: str, applicant: dict[str, Any]) -> ApplicationResult:
        return ApplicationResult(
            provider_reference=f"RC-APP-{uuid.uuid4().hex[:8].upper()}", status="received", is_mock=False
        )

    async def submit_application(self, application_ref: str, documents: list[dict[str, Any]]) -> ApplicationResult:
        # No live API to hand documents to this insurer yet - the staff
        # underwriting queue (/admin/applications) is where a human takes
        # it from here, same as any application awaiting review.
        return ApplicationResult(provider_reference=application_ref, status="under_review", is_mock=False)

    async def make_payment(self, application_ref: str, payment_ref: str) -> dict[str, Any]:
        return {"application_ref": application_ref, "payment_ref": payment_ref, "status": "acknowledged", "is_mock": False}

    async def issue_policy(self, application_ref: str) -> PolicyResult:
        # Binding cover with the real insurer is a manual step until they
        # give us an API - the policy is created as "under_review" so a
        # staff member confirms the real underwriter has actually bound
        # it before it shows as active to the customer.
        return PolicyResult(
            policy_number=f"RC-POL-{uuid.uuid4().hex[:8].upper()}", status="under_review", documents=[], is_mock=False
        )

    async def get_policy(self, policy_number: str) -> PolicyResult:
        return PolicyResult(policy_number=policy_number, status="under_review", documents=[], is_mock=False)

    async def get_documents(self, policy_number: str) -> list[dict[str, Any]]:
        return []

    async def submit_claim(self, policy_number: str, claim_details: dict[str, Any]) -> ClaimStatusResult:
        return ClaimStatusResult(
            claim_reference=f"RC-CLM-{uuid.uuid4().hex[:8].upper()}",
            status="reported",
            notes="No live claims API for this provider yet - routed to the staff-assisted claims queue.",
            is_mock=False,
        )

    async def get_claim_status(self, claim_reference: str) -> ClaimStatusResult:
        return ClaimStatusResult(claim_reference=claim_reference, status="under_review", is_mock=False)

    async def renew_policy(self, policy_number: str) -> NormalizedQuote:
        return await self.get_quote("motor", {})
