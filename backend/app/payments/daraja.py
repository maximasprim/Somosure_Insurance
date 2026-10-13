"""Safaricom Daraja - M-Pesa Express (STK push).

Flow: initiate() asks Safaricom to pop an M-Pesa PIN prompt on the customer's phone;
Safaricom later POSTs the result to our callback address. Daraja callbacks are NOT
signed, so we do not trust them on their own:

  1. the callback address contains a secret only Safaricom was given (checked in
     app/api/v1/payments.py);
  2. before a payment is marked successful the service calls confirm() - an
     independent "STK Push Query" straight to Safaricom;
  3. the amount reported must equal the amount we asked for;
  4. a periodic reconciliation job (see app/services/scheduler.py) settles payments
     whose callback never arrived, using the same query.

Nothing here runs unless MPESA_MODE=daraja. Start with MPESA_ENV=sandbox.
"""

import logging
import time
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.core.config import Settings, get_settings
from app.payments import daraja_util as du
from app.payments.base import PaymentInitiationResult, PaymentProviderAdapter, WebhookVerificationResult

logger = logging.getLogger("somosure.daraja")

_BASES = {"sandbox": "https://sandbox.safaricom.co.ke", "production": "https://api.safaricom.co.ke"}
_token_cache: dict[str, tuple[str, float]] = {}  # base url -> (token, expires_at)


class DarajaMpesaProvider(PaymentProviderAdapter):
    is_mock = False

    def __init__(self, settings: Settings | None = None):
        s = settings or get_settings()
        missing = [
            name
            for name, value in (
                ("MPESA_CONSUMER_KEY", s.mpesa_consumer_key),
                ("MPESA_CONSUMER_SECRET", s.mpesa_consumer_secret),
                ("MPESA_SHORTCODE", s.mpesa_shortcode),
                ("MPESA_PASSKEY", s.mpesa_passkey),
                ("MPESA_CALLBACK_BASE_URL", s.mpesa_callback_base_url),
                ("MPESA_CALLBACK_SECRET", s.mpesa_callback_secret),
            )
            if not value
        ]
        if missing:
            logger.error("M-Pesa is switched on but not configured: missing %s", ", ".join(missing))
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "M-Pesa payments are not available right now. Please contact us.")
        if s.mpesa_env not in _BASES:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "M-Pesa payments are not available right now. Please contact us.")
        self.s = s
        self.base = _BASES[s.mpesa_env]

    # -- auth ---------------------------------------------------------------

    async def _token(self, client: httpx.AsyncClient) -> str:
        cached = _token_cache.get(self.base)
        if cached and cached[1] > time.time() + 30:
            return cached[0]
        resp = await client.get(
            f"{self.base}/oauth/v1/generate",
            params={"grant_type": "client_credentials"},
            auth=(self.s.mpesa_consumer_key, self.s.mpesa_consumer_secret),
        )
        resp.raise_for_status()
        data = resp.json()
        token = data["access_token"]
        _token_cache[self.base] = (token, time.time() + int(data.get("expires_in", 3599)))
        return token

    def _stk_auth_fields(self) -> dict[str, str]:
        timestamp = du.daraja_timestamp()
        return {
            "BusinessShortCode": self.s.mpesa_shortcode,
            "Password": du.daraja_password(self.s.mpesa_shortcode, self.s.mpesa_passkey, timestamp),
            "Timestamp": timestamp,
        }

    # -- adapter interface -----------------------------------------------------

    async def initiate(self, amount: str, phone: str | None, reference: str) -> PaymentInitiationResult:
        try:
            msisdn = du.normalise_msisdn(phone)
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
        try:
            callback = du.callback_url(self.s.mpesa_callback_base_url, self.s.mpesa_callback_secret)
        except ValueError:
            logger.exception("M-Pesa callback address is not valid")
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "M-Pesa payments are not available right now. Please contact us.")

        shillings = du.whole_shillings(amount)
        payload = {
            **self._stk_auth_fields(),
            "TransactionType": self.s.mpesa_transaction_type,
            "Amount": shillings,
            "PartyA": msisdn,
            "PartyB": self.s.mpesa_shortcode,
            "PhoneNumber": msisdn,
            "CallBackURL": callback,
            "AccountReference": "Somosure",  # shown on the customer's M-Pesa statement (max 12 chars)
            "TransactionDesc": "Insurance",  # max 13 chars
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                token = await self._token(client)
                resp = await client.post(
                    f"{self.base}/mpesa/stkpush/v1/processrequest", json=payload, headers={"Authorization": f"Bearer {token}"}
                )
            body: dict[str, Any] = resp.json()
        except Exception:
            logger.exception("Could not reach M-Pesa to start payment %s", reference)
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "We could not reach M-Pesa. Please try again in a moment.")

        if resp.status_code != 200 or str(body.get("ResponseCode")) != "0" or not body.get("CheckoutRequestID"):
            logger.error("M-Pesa refused to start payment %s: HTTP %s %s", reference, resp.status_code, body)
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "M-Pesa could not send the payment prompt. Check the number and try again.")

        return PaymentInitiationResult(
            provider_transaction_id=body["CheckoutRequestID"],
            status="pending",
            raw={
                "MerchantRequestID": body.get("MerchantRequestID"),
                "CheckoutRequestID": body["CheckoutRequestID"],
                "ResponseDescription": body.get("ResponseDescription"),
                "CustomerMessage": body.get("CustomerMessage"),
                "amount_requested": shillings,
                "reference": reference,
            },
            is_mock=False,
        )

    def verify_webhook(self, headers: dict[str, str], body: bytes) -> WebhookVerificationResult:
        """Reads the callback Safaricom posts. The callback address itself carries our
        secret (checked by the route before this runs); this only parses the body."""
        import json

        try:
            parsed = du.parse_stk_callback(json.loads(body))
        except Exception:
            parsed = None
        if not parsed:
            return WebhookVerificationResult(is_valid=False, provider_transaction_id=None, status=None)
        return WebhookVerificationResult(
            is_valid=True,
            provider_transaction_id=parsed["checkout_id"],
            status="successful" if parsed["result_code"] == 0 else "failed",
            amount=str(parsed["amount"]) if parsed["amount"] is not None else None,
            raw=parsed,
        )

    async def confirm(self, provider_transaction_id: str) -> WebhookVerificationResult | None:
        payload = {**self._stk_auth_fields(), "CheckoutRequestID": provider_transaction_id}
        async with httpx.AsyncClient(timeout=30.0) as client:
            token = await self._token(client)
            resp = await client.post(
                f"{self.base}/mpesa/stkpushquery/v1/query", json=payload, headers={"Authorization": f"Bearer {token}"}
            )
        try:
            body = resp.json()
        except Exception:
            body = {}
        outcome, details = du.interpret_query_response(body if resp.status_code == 200 else {})
        return WebhookVerificationResult(is_valid=True, provider_transaction_id=provider_transaction_id, status=outcome, raw=details)

    def amount_matches(self, reported_amount, expected_amount) -> bool:
        return du.amounts_match(reported_amount, expected_amount)
