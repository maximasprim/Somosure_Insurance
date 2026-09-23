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

# Stands in for "the ~25 insurers Lami bridges" at a demo-able scale - three
# clearly-labeled demo underwriters, so the multi-quote-per-provider-row
# architecture (docs/PROVIDER_LANDSCAPE.md) can be exercised and verified
# without needing Lami's real API.
_DEMO_UNDERLYING_INSURERS = ["Demo Underwriter X", "Demo Underwriter Y", "Demo Underwriter Z"]

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


class MockAggregatorProvider(InsuranceProviderAdapter):
    """Demonstrates what a real Lami/mTek/Turaco integration should do:
    ONE call returns quotes from SEVERAL underlying insurers. This is what
    actually gets exercised by the quote engine today (see
    app/services/quote_service.py calling get_quotes_bulk() for every
    provider) - proving the architecture works before any real aggregator
    credentials exist, not just documenting that it should."""

    is_mock = True

    def __init__(self, provider_id: str, display_name: str = "Demo Aggregator"):
        self.provider_id = provider_id
        self.display_name = display_name

    async def get_products(self) -> list[dict[str, Any]]:
        return [
            {"category": cat, "name": f"{insurer} {cat.title()} Cover (via {self.display_name})"}
            for cat in _BASE_RATES
            for insurer in _DEMO_UNDERLYING_INSURERS
        ]

    def _quote_for(self, product_category: str, underlying_name: str) -> NormalizedQuote:
        base = _BASE_RATES.get(product_category, Decimal("10000"))
        index = _DEMO_UNDERLYING_INSURERS.index(underlying_name)
        hash_component = int(hashlib.sha256(f"{self.provider_id}-{underlying_name}".encode()).hexdigest(), 16) % 15
        variance = index * 20 + hash_component  # index spacing (20) exceeds hash range (0-14) so ranges never overlap
        premium = (base * (Decimal("0.85") + Decimal(variance) / 100)).quantize(Decimal("0.01"))
        taxes = (premium * Decimal("0.16")).quantize(Decimal("0.01"))
        fees = Decimal("350.00")
        total = (premium + taxes + fees).quantize(Decimal("0.01"))

        return NormalizedQuote(
            provider_id=self.provider_id,
            product_category=product_category,
            premium=premium,
            taxes=taxes,
            fees=fees,
            total=total,
            coverage={"summary": f"Standard {product_category} cover underwritten by {underlying_name}"},
            exclusions={"items": ["Wear and tear", "Pre-existing conditions"]},
            deductibles={"excess": "10% of claim, min KES 5,000"},
            payment_options={"methods": ["mpesa", "card"], "installments_allowed": True},
            metadata={"aggregator": self.display_name, "underlying_insurer": underlying_name},
            underlying_provider_name=underlying_name,
            valid_until=datetime.now(timezone.utc) + timedelta(days=14),
            is_mock=True,
        )

    async def get_quote(self, product_category: str, answers: dict[str, Any]) -> NormalizedQuote:
        # Interface compatibility only - real callers should use
        # get_quotes_bulk() to see every underlying insurer, which is the
        # entire point of integrating with an aggregator.
        return self._quote_for(product_category, _DEMO_UNDERLYING_INSURERS[0])

    async def get_quotes_bulk(self, product_category: str, answers: dict[str, Any]) -> list[NormalizedQuote]:
        return [self._quote_for(product_category, name) for name in _DEMO_UNDERLYING_INSURERS]

    async def create_application(self, quote_ref: str, applicant: dict[str, Any]) -> ApplicationResult:
        return ApplicationResult(provider_reference=f"MOCK-AGG-APP-{uuid.uuid4().hex[:8].upper()}", status="received")

    async def submit_application(self, application_ref: str, documents: list[dict[str, Any]]) -> ApplicationResult:
        return ApplicationResult(provider_reference=application_ref, status="under_review")

    async def make_payment(self, application_ref: str, payment_ref: str) -> dict[str, Any]:
        return {"application_ref": application_ref, "payment_ref": payment_ref, "status": "acknowledged", "is_mock": True}

    async def issue_policy(self, application_ref: str) -> PolicyResult:
        return PolicyResult(policy_number=f"MOCK-AGG-POL-{uuid.uuid4().hex[:8].upper()}", status="active", documents=[])

    async def get_policy(self, policy_number: str) -> PolicyResult:
        return PolicyResult(policy_number=policy_number, status="active", documents=[])

    async def get_documents(self, policy_number: str) -> list[dict[str, Any]]:
        return []

    async def submit_claim(self, policy_number: str, claim_details: dict[str, Any]) -> ClaimStatusResult:
        return ClaimStatusResult(claim_reference=f"MOCK-AGG-CLM-{uuid.uuid4().hex[:8].upper()}", status="reported")

    async def get_claim_status(self, claim_reference: str) -> ClaimStatusResult:
        return ClaimStatusResult(claim_reference=claim_reference, status="under_review")

    async def renew_policy(self, policy_number: str) -> NormalizedQuote:
        return self._quote_for("motor", _DEMO_UNDERLYING_INSURERS[0])
