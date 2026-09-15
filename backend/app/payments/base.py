"""PaymentProviderAdapter - mirrors the InsuranceProviderAdapter pattern
from app/providers/base.py so payment methods (M-Pesa, card, bank transfer)
are as swappable as insurers are, per spec §13's payment abstraction layer.

The backend NEVER marks a payment successful based on a frontend call -
only a verified webhook (verify_webhook) or an explicit reconciliation
action can do that. initiate() only ever returns a "pending" state.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PaymentInitiationResult:
    provider_transaction_id: str
    status: str  # always "pending" immediately after initiation
    raw: dict[str, Any] = field(default_factory=dict)
    is_mock: bool = True


@dataclass
class WebhookVerificationResult:
    is_valid: bool
    provider_transaction_id: str | None
    status: str | None  # successful | failed
    amount: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class PaymentProviderAdapter(ABC):
    is_mock: bool = True

    @abstractmethod
    async def initiate(self, amount: str, phone: str | None, reference: str) -> PaymentInitiationResult: ...

    @abstractmethod
    def verify_webhook(self, headers: dict[str, str], body: bytes) -> WebhookVerificationResult:
        """Must verify signature/shared-secret before trusting body content.
        Real adapters reject anything that doesn't verify; never assume
        webhook payloads are trustworthy just because they arrived."""
