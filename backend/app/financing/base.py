"""CreditProviderAdapter - mirrors InsuranceProviderAdapter (app/providers/
base.py) and PaymentProviderAdapter (app/payments/base.py): financing
partners are swappable the same way insurers and payment methods are.

Bidii Credit is a confirmed, existing business partnership (per the
person building this platform), which is why this module is built as a
complete, working feature rather than the "built but switched off"
treatment Phase 8 originally called for when financing was a hypothetical
partner. What's still genuinely missing is Bidii's actual API
documentation and credentials - no real endpoint, request/response shape,
or auth scheme is invented here. MockBidiiCreditAdapter implements the
full interface with clearly-labeled simulated data so the eligibility →
application → agreement → installment flow is real and testable; swapping
in real Bidii API calls means implementing this same interface against
their real spec, exactly like BritamAdapter or DarajaMpesaProvider would.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass
class CreditEligibilityResult:
    eligible: bool
    max_financed_amount: Decimal | None = None
    reason: str | None = None
    is_mock: bool = True


@dataclass
class CreditApplicationResult:
    provider_reference: str
    status: str  # submitted | approved | rejected
    reason: str | None = None
    is_mock: bool = True


class CreditProviderAdapter(ABC):
    is_mock: bool = True

    @abstractmethod
    async def check_eligibility(self, customer_context: dict[str, Any], amount: Decimal) -> CreditEligibilityResult: ...

    @abstractmethod
    async def submit_application(self, application_reference: str, customer_context: dict[str, Any], financed_amount: Decimal, term_months: int) -> CreditApplicationResult: ...

    @abstractmethod
    async def get_application_status(self, provider_reference: str) -> CreditApplicationResult: ...
