import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from app.providers.base import (
    ApplicationResult,
    ClaimStatusResult,
    InsuranceProviderAdapter,
    NormalizedQuote,
    PolicyResult,
)

# Deterministic base rates by product category, purely for demo/dev purposes.
# These are NOT actuarial figures and must never be presented to a real
# customer as a real premium - the is_mock flag on every return value exists
# specifically to prevent that.
_BASE_RATES: dict[str, Decimal] = {
    "motor": Decimal("18000"),
    "medical": Decimal("35000"),
    "personal_accident": Decimal("6000"),
    "travel": Decimal("4000"),
    "home": Decimal("12000"),
    "life": Decimal("20000"),
    "business": Decimal("50000"),
    "professional_indemnity": Decimal("28000"),
    "wiba": Decimal("15000"),
}


class MockProvider(InsuranceProviderAdapter):
    """Deterministic stand-in used in dev/staging so the quote engine, UI,
    and downstream flows (application, payment, policy) can be built and
    tested before any real insurer contract exists."""

    is_mock = True

    def __init__(self, provider_id: str, display_name: str = "Mock Insurer"):
        self.provider_id = provider_id
        self.display_name = display_name

    async def get_products(self) -> list[dict[str, Any]]:
        return [{"category": cat, "name": f"{self.display_name} {cat.title()} Cover"} for cat in _BASE_RATES]

    async def get_quote(self, product_category: str, answers: dict[str, Any]) -> NormalizedQuote:
        base = _BASE_RATES.get(product_category, Decimal("10000"))
        # Deterministic variance per provider so multiple mock providers in a
        # comparison table don't all show identical numbers.
        variance = int(hashlib.sha256(self.provider_id.encode()).hexdigest(), 16) % 20
        premium = base * (Decimal("0.9") + Decimal(variance) / 100)
        taxes = (premium * Decimal("0.16")).quantize(Decimal("0.01"))
        fees = Decimal("500.00")
        total = (premium + taxes + fees).quantize(Decimal("0.01"))

        return NormalizedQuote(
            provider_id=self.provider_id,
            product_category=product_category,
            premium=premium.quantize(Decimal("0.01")),
            taxes=taxes,
            fees=fees,
            total=total,
            coverage={"summary": f"Standard {product_category} cover"},
            exclusions={"items": ["Wear and tear", "Pre-existing conditions"]},
            deductibles={"excess": "10% of claim, min KES 5,000"},
            payment_options={"methods": ["mpesa", "card", "bank_transfer"], "installments_allowed": True},
            metadata={"provider_name": self.display_name},
            valid_until=datetime.now(timezone.utc) + timedelta(days=14),
            is_mock=True,
        )

    async def create_application(self, quote_ref: str, applicant: dict[str, Any]) -> ApplicationResult:
        return ApplicationResult(provider_reference=f"MOCK-APP-{uuid.uuid4().hex[:8].upper()}", status="received")

    async def submit_application(self, application_ref: str, documents: list[dict[str, Any]]) -> ApplicationResult:
        return ApplicationResult(provider_reference=application_ref, status="under_review")

    async def make_payment(self, application_ref: str, payment_ref: str) -> dict[str, Any]:
        return {"application_ref": application_ref, "payment_ref": payment_ref, "status": "acknowledged", "is_mock": True}

    async def issue_policy(self, application_ref: str) -> PolicyResult:
        return PolicyResult(policy_number=f"MOCK-POL-{uuid.uuid4().hex[:8].upper()}", status="active", documents=[])

    async def get_policy(self, policy_number: str) -> PolicyResult:
        return PolicyResult(policy_number=policy_number, status="active", documents=[])

    async def get_documents(self, policy_number: str) -> list[dict[str, Any]]:
        return []

    async def submit_claim(self, policy_number: str, claim_details: dict[str, Any]) -> ClaimStatusResult:
        return ClaimStatusResult(claim_reference=f"MOCK-CLM-{uuid.uuid4().hex[:8].upper()}", status="reported")

    async def get_claim_status(self, claim_reference: str) -> ClaimStatusResult:
        return ClaimStatusResult(claim_reference=claim_reference, status="under_review")

    async def renew_policy(self, policy_number: str) -> NormalizedQuote:
        return await self.get_quote("motor", {})
