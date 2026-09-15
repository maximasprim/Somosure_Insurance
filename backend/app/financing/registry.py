"""Resolves the configured credit partner to a live adapter. A real
BidiiCreditAdapter gets registered here once real API docs/credentials
exist - nothing else in the financing module changes.
"""

from app.financing.base import CreditProviderAdapter
from app.financing.mock_bidii import MockBidiiCreditAdapter

_REAL_PROVIDER: type[CreditProviderAdapter] | None = None


def get_credit_provider() -> CreditProviderAdapter:
    if _REAL_PROVIDER:
        return _REAL_PROVIDER()
    return MockBidiiCreditAdapter()
