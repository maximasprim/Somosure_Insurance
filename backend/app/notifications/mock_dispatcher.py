import logging
import uuid

from app.notifications.base import DispatchResult, NotificationDispatcher

logger = logging.getLogger("somosure.notifications")


class MockDispatcher(NotificationDispatcher):
    """No real SMS/email credentials exist yet. Logs the outbound message
    at INFO level (visible in application logs, useful for dev/demo) and
    returns delivered=True with is_mock=True - never presented as a real
    delivery confirmation anywhere it's surfaced (Notification.status
    still means "recorded", not "confirmed delivered by a real carrier",
    until a real dispatcher replaces this)."""

    is_mock = True

    async def send_sms(self, phone: str, body: str) -> DispatchResult:
        logger.info("[MOCK SMS] to=%s body=%s", phone, body)
        return DispatchResult(delivered=True, provider_message_id=f"MOCK-SMS-{uuid.uuid4().hex[:8]}", is_mock=True)

    async def send_email(self, email: str, subject: str, body: str) -> DispatchResult:
        logger.info("[MOCK EMAIL] to=%s subject=%s body=%s", email, subject, body)
        return DispatchResult(delivered=True, provider_message_id=f"MOCK-EMAIL-{uuid.uuid4().hex[:8]}", is_mock=True)
