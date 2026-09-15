"""Resolves the configured SMS dispatcher. Real credentials (Africa's
Talking) activate AfricasTalkingDispatcher; otherwise falls back to the
mock so dev/demo environments always work.
"""

from app.core.config import get_settings
from app.notifications.africastalking_dispatcher import AfricasTalkingDispatcher
from app.notifications.base import NotificationDispatcher
from app.notifications.mock_dispatcher import MockDispatcher

settings = get_settings()


def get_dispatcher() -> NotificationDispatcher:
    if settings.africastalking_api_key and settings.africastalking_username:
        return AfricasTalkingDispatcher(settings.africastalking_api_key, settings.africastalking_username)
    return MockDispatcher()
