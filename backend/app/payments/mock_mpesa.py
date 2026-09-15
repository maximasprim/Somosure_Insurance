"""Mock M-Pesa adapter.

No Safaricom Daraja credentials exist yet (spec §51 - never fabricate a
real payment confirmation), so this adapter simulates the STK push and
callback round-trip locally: initiate() returns a pending transaction, and
a companion endpoint lets the dev/demo environment simulate the customer
completing payment on their phone, which posts a signed callback back to
our own webhook - exercising the exact signature-verification path a real
Daraja integration would need, not skipping it.
"""

import hashlib
import hmac
import json
import uuid
from typing import Any

from app.core.config import get_settings
from app.payments.base import PaymentInitiationResult, PaymentProviderAdapter, WebhookVerificationResult

settings = get_settings()

# Dev-only shared secret for signing simulated callbacks. A real Daraja
# integration authenticates callbacks differently (IP allowlisting +
# consumer key/secret on the outbound STK call) - this HMAC exists purely
# so the mock exercises a real verify-before-trust code path.
_MOCK_WEBHOOK_SECRET = "mock-mpesa-dev-secret"


def _sign(payload: bytes) -> str:
    return hmac.new(_MOCK_WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()


class MockMpesaProvider(PaymentProviderAdapter):
    is_mock = True

    async def initiate(self, amount: str, phone: str | None, reference: str) -> PaymentInitiationResult:
        checkout_id = f"MOCK-CHK-{uuid.uuid4().hex[:10].upper()}"
        return PaymentInitiationResult(
            provider_transaction_id=checkout_id,
            status="pending",
            raw={"amount": amount, "phone": phone, "reference": reference},
            is_mock=True,
        )

    def build_simulated_callback(self, checkout_id: str, outcome: str, amount: str) -> tuple[bytes, dict[str, str]]:
        """Used only by the dev "simulate payment" endpoint - builds a
        signed payload identical in shape to what the real webhook route
        expects, so the same verify_webhook path runs either way."""
        body = json.dumps(
            {
                "CheckoutRequestID": checkout_id,
                "ResultCode": 0 if outcome == "successful" else 1,
                "Amount": amount,
                "MpesaReceiptNumber": f"MOCK{uuid.uuid4().hex[:8].upper()}" if outcome == "successful" else None,
            }
        ).encode()
        signature = _sign(body)
        return body, {"X-Mock-Signature": signature}

    def verify_webhook(self, headers: dict[str, str], body: bytes) -> WebhookVerificationResult:
        signature = headers.get("X-Mock-Signature") or headers.get("x-mock-signature")
        if not signature or not hmac.compare_digest(signature, _sign(body)):
            return WebhookVerificationResult(is_valid=False, provider_transaction_id=None, status=None)

        payload: dict[str, Any] = json.loads(body)
        status = "successful" if payload.get("ResultCode") == 0 else "failed"
        return WebhookVerificationResult(
            is_valid=True,
            provider_transaction_id=payload.get("CheckoutRequestID"),
            status=status,
            amount=str(payload.get("Amount")) if payload.get("Amount") is not None else None,
            raw=payload,
        )
