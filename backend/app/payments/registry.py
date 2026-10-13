"""Resolves a payment method string to a live PaymentProviderAdapter.

M-Pesa is served by the real Daraja integration when MPESA_MODE=daraja. The
built-in simulator (MockMpesaProvider) is only available outside production, or when
ALLOW_MOCK_PAYMENTS=true is set on purpose: its callback-signing secret is public in
the repository, so on a live server it would let anyone fake a successful payment.
"""

from fastapi import HTTPException, status

from app.core.config import Settings, get_settings
from app.payments.base import PaymentProviderAdapter
from app.payments.mock_mpesa import MockMpesaProvider


def mock_payments_allowed(settings: Settings | None = None) -> bool:
    s = settings or get_settings()
    return s.environment != "production" or s.allow_mock_payments


def mpesa_is_mock(settings: Settings | None = None) -> bool:
    s = settings or get_settings()
    return s.mpesa_mode != "daraja"


def get_payment_provider(method: str) -> PaymentProviderAdapter:
    if method == "mpesa":
        s = get_settings()
        if s.mpesa_mode == "daraja":
            from app.payments.daraja import DarajaMpesaProvider

            return DarajaMpesaProvider(s)
        if mock_payments_allowed(s):
            return MockMpesaProvider()
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Online payment is not switched on yet. Please contact us to pay.",
        )
    raise NotImplementedError(f"No payment provider configured for method '{method}' yet")
