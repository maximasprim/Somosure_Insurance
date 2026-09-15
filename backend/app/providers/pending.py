"""Base class for adapters representing a real, named company we intend to
integrate with but don't yet have API documentation or credentials for.

Every method raises NotImplementedError naming exactly what's missing
rather than returning any fabricated data - this is the mechanism, not
just the intent, behind spec §51's "do not invent API endpoints or
credentials" rule. Subclasses set PROVIDER_LABEL and WHAT_IS_KNOWN; see
docs/PROVIDER_LANDSCAPE.md for the research behind each one.
"""

from typing import Any

from app.providers.base import (
    ApplicationResult,
    ClaimStatusResult,
    InsuranceProviderAdapter,
    NormalizedQuote,
    PolicyResult,
)


class PendingIntegrationAdapter(InsuranceProviderAdapter):
    PROVIDER_LABEL: str = "This provider"
    WHAT_IS_KNOWN: str = "No public integration details found."
    is_mock = True  # never claims to be a real integration until overridden

    def __init__(self, provider_id: str):
        self.provider_id = provider_id

    def _not_ready(self, method: str) -> NotImplementedError:
        return NotImplementedError(
            f"{self.PROVIDER_LABEL} adapter's {method}() is not implemented - "
            f"no API documentation or credentials exist yet. {self.WHAT_IS_KNOWN} "
            f"See docs/PROVIDER_LANDSCAPE.md and docs/API_ACCESS_REQUEST_TEMPLATE.md."
        )

    async def get_products(self) -> list[dict[str, Any]]:
        raise self._not_ready("get_products")

    async def get_quote(self, product_category: str, answers: dict[str, Any]) -> NormalizedQuote:
        raise self._not_ready("get_quote")

    async def create_application(self, quote_ref: str, applicant: dict[str, Any]) -> ApplicationResult:
        raise self._not_ready("create_application")

    async def submit_application(self, application_ref: str, documents: list[dict[str, Any]]) -> ApplicationResult:
        raise self._not_ready("submit_application")

    async def make_payment(self, application_ref: str, payment_ref: str) -> dict[str, Any]:
        raise self._not_ready("make_payment")

    async def issue_policy(self, application_ref: str) -> PolicyResult:
        raise self._not_ready("issue_policy")

    async def get_policy(self, policy_number: str) -> PolicyResult:
        raise self._not_ready("get_policy")

    async def get_documents(self, policy_number: str) -> list[dict[str, Any]]:
        raise self._not_ready("get_documents")

    async def submit_claim(self, policy_number: str, claim_details: dict[str, Any]) -> ClaimStatusResult:
        raise self._not_ready("submit_claim")

    async def get_claim_status(self, claim_reference: str) -> ClaimStatusResult:
        raise self._not_ready("get_claim_status")

    async def renew_policy(self, policy_number: str) -> NormalizedQuote:
        raise self._not_ready("renew_policy")
