import logging
import uuid
from typing import Any

from app.whatsapp.base import WhatsAppAdapter, WhatsAppSendResult

logger = logging.getLogger("somosure.whatsapp")


class MockWhatsAppAdapter(WhatsAppAdapter):
    """No real WABA ID/access token exists yet - logs what would be sent.
    The receiving side (webhook verification) is real; only sending is
    mocked here, since sending requires a real Meta Business Manager
    account and approved templates (see docs/WHATSAPP.md)."""

    is_mock = True

    async def send_text_message(self, to_phone: str, body: str) -> WhatsAppSendResult:
        logger.info("[MOCK WHATSAPP text] to=%s body=%s", to_phone, body)
        return WhatsAppSendResult(provider_message_id=f"MOCK-WA-{uuid.uuid4().hex[:8]}", is_mock=True)

    async def send_template_message(self, to_phone: str, template_name: str, params: dict[str, Any]) -> WhatsAppSendResult:
        logger.info("[MOCK WHATSAPP template] to=%s template=%s params=%s", to_phone, template_name, params)
        return WhatsAppSendResult(provider_message_id=f"MOCK-WA-{uuid.uuid4().hex[:8]}", is_mock=True)
