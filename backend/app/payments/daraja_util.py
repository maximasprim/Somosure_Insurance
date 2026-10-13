"""Pure helpers for Safaricom Daraja (M-Pesa Express / STK push).

Kept free of any web-framework or settings imports so the formats Safaricom is
strict about (timestamp, password, phone, whole-shilling amount, callback shape)
can be tested on their own.
"""

import base64
import re
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

EAT = timezone(timedelta(hours=3))  # East Africa Time, no daylight saving

# Safaricom refuses callback URLs that contain these words.
FORBIDDEN_CALLBACK_WORDS = ("mpesa", "safaricom", "daraja", "exec", "cmd", "sql", "query")


def daraja_timestamp(now: datetime | None = None) -> str:
    return (now or datetime.now(EAT)).astimezone(EAT).strftime("%Y%m%d%H%M%S")


def daraja_password(shortcode: str, passkey: str, timestamp: str) -> str:
    return base64.b64encode(f"{shortcode}{passkey}{timestamp}".encode()).decode()


def normalise_msisdn(phone: str | None) -> str:
    """2547XXXXXXXX / 2541XXXXXXXX, which is the only form Daraja accepts."""
    digits = re.sub(r"\D", "", phone or "")
    # Safaricom numbers are 07XX... and 01XX... (so 2547... / 2541... in full).
    if digits.startswith("254") and len(digits) == 12 and digits[3] in "17":
        return digits
    if digits.startswith("0") and len(digits) == 10 and digits[1] in "17":
        return "254" + digits[1:]
    if len(digits) == 9 and digits[0] in "17":
        return "254" + digits
    raise ValueError("Enter a valid Safaricom number, for example 0712 345 678")


def whole_shillings(amount: Any) -> int:
    """Daraja takes whole shillings. Rounds half up; never below 1."""
    value = Decimal(str(amount)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return max(int(value), 1)


def amounts_match(callback_amount: Any, expected_amount: Any) -> bool:
    try:
        return Decimal(str(callback_amount)) == Decimal(whole_shillings(expected_amount))
    except Exception:
        return False


def callback_url(base_url: str, secret: str) -> str:
    base = (base_url or "").strip().rstrip("/")
    if not base.startswith("https://"):
        raise ValueError("MPESA_CALLBACK_BASE_URL must be a public https:// address")
    if not secret or len(secret) < 16:
        raise ValueError("MPESA_CALLBACK_SECRET must be a random string of at least 16 characters")
    url = f"{base}/api/v1/webhooks/pay/{secret}"
    lowered = url.lower()
    bad = [w for w in FORBIDDEN_CALLBACK_WORDS if w in lowered]
    if bad:
        raise ValueError(f"Safaricom rejects callback addresses containing {bad} - change the base URL or secret")
    return url


def parse_stk_callback(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Reads the body Safaricom posts after the customer answers the prompt.
    Returns {checkout_id, result_code, result_desc, amount, receipt, phone}, or None
    when the body isn't the expected shape."""
    try:
        cb = payload["Body"]["stkCallback"]
        checkout_id = cb["CheckoutRequestID"]
        result_code = int(cb["ResultCode"])
    except (KeyError, TypeError, ValueError):
        return None
    items = {}
    for item in ((cb.get("CallbackMetadata") or {}).get("Item") or []):
        if isinstance(item, dict) and "Name" in item:
            items[item["Name"]] = item.get("Value")
    return {
        "checkout_id": checkout_id,
        "result_code": result_code,
        "result_desc": cb.get("ResultDesc"),
        "amount": items.get("Amount"),
        "receipt": items.get("MpesaReceiptNumber"),
        "phone": items.get("PhoneNumber"),
    }


# STK Push Query: while the customer is still deciding, Safaricom answers with an
# error-style body (HTTP 500, "The transaction is being processed") that has no
# ResultCode - that is "no final answer yet", not a failure.


def interpret_query_response(body: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    """('successful' | 'failed' | None, details) from an STK Push Query response.
    None means "no final answer yet" - leave the payment pending."""
    if "ResultCode" in body:
        try:
            code = int(body["ResultCode"])
        except (TypeError, ValueError):
            return None, body
        return ("successful" if code == 0 else "failed"), body
    return None, body
