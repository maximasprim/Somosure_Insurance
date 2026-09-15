"""WhatsAppAdapter - mirrors every other adapter pattern in this codebase.

Unlike the insurer/payment adapters, the webhook verification pieces here
are REAL, not mocked - see verify_subscription_challenge() and
verify_signature() below. Both only depend on values this application
itself controls (a verify token, an app secret), not on Meta's approval,
so there's nothing to fake: point a real Meta app's webhook config at
this endpoint and it works as-is. Only sending messages via Graph API
needs a real WABA ID and access token.
"""

import hashlib
import hmac
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class WhatsAppSendResult:
    provider_message_id: str
    is_mock: bool = True


class WhatsAppAdapter(ABC):
    is_mock: bool = True

    @abstractmethod
    async def send_text_message(self, to_phone: str, body: str) -> WhatsAppSendResult:
        """Only valid within the 24-hour customer service window (a
        customer messaged in the last 24h) - outside that window, Meta
        requires send_template_message with a pre-approved template."""

    @abstractmethod
    async def send_template_message(self, to_phone: str, template_name: str, params: dict[str, Any]) -> WhatsAppSendResult: ...


def verify_subscription_challenge(mode: str | None, verify_token: str | None, challenge: str | None, expected_token: str) -> str | None:
    """Meta's real webhook setup verification (GET request). Returns the
    challenge string to echo back if valid, None if the request should be
    rejected. This exact logic is what Meta's App Dashboard actually
    calls when you configure a webhook URL - no mocking involved."""
    if mode == "subscribe" and verify_token == expected_token and challenge:
        return challenge
    return None


def verify_signature(app_secret: str, payload: bytes, signature_header: str | None) -> bool:
    """Meta's real payload signature scheme: X-Hub-Signature-256 is
    'sha256=' + HMAC-SHA256(app_secret, payload) in hex. Genuinely
    implemented - this is exactly what Meta computes and sends on every
    webhook POST once a real app secret is configured."""
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), payload, hashlib.sha256).hexdigest()
    provided = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, provided)
