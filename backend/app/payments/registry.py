"""Resolves a payment method string to a live PaymentProviderAdapter.
Real adapters (DarajaMpesaProvider, a card gateway, ...) register here once
credentials exist - nothing else in the codebase changes.
"""

from app.payments.base import PaymentProviderAdapter
from app.payments.mock_mpesa import MockMpesaProvider

_REAL_PROVIDERS: dict[str, type[PaymentProviderAdapter]] = {}


def get_payment_provider(method: str) -> PaymentProviderAdapter:
    if method in _REAL_PROVIDERS:
        return _REAL_PROVIDERS[method]()
    if method == "mpesa":
        return MockMpesaProvider()
    raise NotImplementedError(f"No payment provider configured for method '{method}' yet")
