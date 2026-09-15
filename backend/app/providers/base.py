"""InsuranceProviderAdapter - the interface every insurer/broker integration
implements, so the rest of the platform never talks to a provider's raw API
shape (spec §5, §33).

Real adapters (BritamAdapter, JubileeAdapter, ...) are added only once the
provider's actual API documentation and credentials are supplied. Until then,
MockProvider is the only concrete implementation, and every quote it returns
is flagged is_mock=True end to end - in the DB row, the API response, and the
UI. This is a hard rule from the spec (§51): never fabricate a real quote,
policy, claim status, or payment confirmation.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass
class NormalizedQuote:
    provider_id: str
    product_category: str
    premium: Decimal
    taxes: Decimal
    fees: Decimal
    total: Decimal
    currency: str = "KES"
    coverage: dict[str, Any] = field(default_factory=dict)
    exclusions: dict[str, Any] = field(default_factory=dict)
    deductibles: dict[str, Any] = field(default_factory=dict)
    payment_options: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    valid_until: datetime | None = None
    is_mock: bool = True
    underlying_provider_name: str | None = None
    # Set when this quote came through an aggregator (Lami, mTek, Turaco)
    # rather than directly from the insurer whose row this is stored
    # against - e.g. provider_id points at the "Lami Technologies" row,
    # but underlying_provider_name is "Britam". None for a direct insurer
    # adapter, where the provider row IS the insurer.


@dataclass
class ApplicationResult:
    provider_reference: str
    status: str
    is_mock: bool = True


@dataclass
class PolicyResult:
    policy_number: str
    status: str
    documents: list[dict[str, Any]] = field(default_factory=list)
    is_mock: bool = True


@dataclass
class ClaimStatusResult:
    claim_reference: str
    status: str
    notes: str | None = None
    is_mock: bool = True


class InsuranceProviderAdapter(ABC):
    """One instance per configured InsuranceProvider row."""

    provider_id: str
    is_mock: bool = True

    @abstractmethod
    async def get_products(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def get_quote(self, product_category: str, answers: dict[str, Any]) -> NormalizedQuote: ...

    async def get_quotes_bulk(self, product_category: str, answers: dict[str, Any]) -> list["NormalizedQuote"]:
        """Returns every quote this provider row can produce for one
        request. For a direct insurer, that's always exactly one quote -
        the default implementation below covers that case by wrapping
        get_quote(), so single-insurer adapters never need to override
        this.

        Aggregators (Lami, mTek, Turaco) DO override this: one real API
        call to an aggregator is expected to return quotes from several
        underlying insurers at once (Lami reportedly bridges ~25), which
        is the entire point of integrating with an aggregator rather than
        each insurer individually - see docs/PROVIDER_LANDSCAPE.md. The
        quote engine (app/services/quote_service.py) calls this method for
        every provider, aggregator or not, and persists one Quote row per
        item returned - so a single aggregator provider row can still
        surface many comparison rows to the customer.
        """
        return [await self.get_quote(product_category, answers)]

    @abstractmethod
    async def create_application(self, quote_ref: str, applicant: dict[str, Any]) -> ApplicationResult: ...

    @abstractmethod
    async def submit_application(self, application_ref: str, documents: list[dict[str, Any]]) -> ApplicationResult: ...

    @abstractmethod
    async def make_payment(self, application_ref: str, payment_ref: str) -> dict[str, Any]: ...

    @abstractmethod
    async def issue_policy(self, application_ref: str) -> PolicyResult: ...

    @abstractmethod
    async def get_policy(self, policy_number: str) -> PolicyResult: ...

    @abstractmethod
    async def get_documents(self, policy_number: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def submit_claim(self, policy_number: str, claim_details: dict[str, Any]) -> ClaimStatusResult: ...

    @abstractmethod
    async def get_claim_status(self, claim_reference: str) -> ClaimStatusResult: ...

    @abstractmethod
    async def renew_policy(self, policy_number: str) -> NormalizedQuote: ...
