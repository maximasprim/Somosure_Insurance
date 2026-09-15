"""Bidii Credit adapter.

Bidii Credit is Somosure's confirmed premium-financing partner. This
adapter is a deterministic mock, not because the partnership is
hypothetical, but because this codebase doesn't have Bidii's real API
documentation, base URL, or credentials - those need to come from Bidii's
technical team the same way any real integration's specifics do. Building
the eligibility/application/status flow against a mock means the rest of
the platform (routes, schemas, frontend, admin portfolio view) is real and
ready the moment those details arrive; only this file's method bodies
change.

Simple, transparent eligibility rule for the mock: approve financing for
amounts up to KES 200,000 for any customer, matching the spec's own
worked example (§14: 20% deposit / 80% financed, KES 30,000 premium).
Replace with Bidii's actual credit/affordability check once available -
do not treat this threshold as a real underwriting rule.
"""

import uuid
from decimal import Decimal
from typing import Any

from app.financing.base import CreditApplicationResult, CreditEligibilityResult, CreditProviderAdapter

MOCK_MAX_FINANCED_AMOUNT = Decimal("200000")


class MockBidiiCreditAdapter(CreditProviderAdapter):
    is_mock = True

    async def check_eligibility(self, customer_context: dict[str, Any], amount: Decimal) -> CreditEligibilityResult:
        if amount > MOCK_MAX_FINANCED_AMOUNT:
            return CreditEligibilityResult(
                eligible=False,
                max_financed_amount=MOCK_MAX_FINANCED_AMOUNT,
                reason=f"Requested amount exceeds the mock eligibility ceiling of KES {MOCK_MAX_FINANCED_AMOUNT:,.0f}",
                is_mock=True,
            )
        return CreditEligibilityResult(eligible=True, max_financed_amount=MOCK_MAX_FINANCED_AMOUNT, is_mock=True)

    async def submit_application(
        self, application_reference: str, customer_context: dict[str, Any], financed_amount: Decimal, term_months: int
    ) -> CreditApplicationResult:
        return CreditApplicationResult(
            provider_reference=f"MOCK-BIDII-{uuid.uuid4().hex[:8].upper()}",
            status="approved",
            is_mock=True,
        )

    async def get_application_status(self, provider_reference: str) -> CreditApplicationResult:
        return CreditApplicationResult(provider_reference=provider_reference, status="approved", is_mock=True)
