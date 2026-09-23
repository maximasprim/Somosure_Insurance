"""Resolves the configured dispatchers. Real credentials (Africa's
Talking) activate AfricasTalkingDispatcher for SMS; otherwise falls back
to the mock so dev/demo environments always work.

Email is resolved separately from SMS (get_email_dispatcher, below) -
they are different channels with different providers, and conflating
them is a real bug: AfricasTalkingDispatcher.send_email() raises
NotImplementedError (Africa's Talking doesn't do email), so if
get_dispatcher() were reused for email, configuring SMS credentials for
an unrelated feature would silently break email-based flows like
password reset. Real credentials (SMTP_HOST/USERNAME/PASSWORD, a work
email account) activate SMTPDispatcher for email; otherwise falls back
to the mock, same as SMS.
"""

from app.core.config import get_settings
from app.notifications.africastalking_dispatcher import AfricasTalkingDispatcher
from app.notifications.base import NotificationDispatcher
from app.notifications.mock_dispatcher import MockDispatcher
from app.notifications.smtp_dispatcher import SMTPDispatcher

settings = get_settings()


def get_dispatcher() -> NotificationDispatcher:
    """SMS dispatcher."""
    if settings.africastalking_api_key and settings.africastalking_username:
        return AfricasTalkingDispatcher(settings.africastalking_api_key, settings.africastalking_username)
    return MockDispatcher()


def get_email_dispatcher() -> NotificationDispatcher:
    """Email dispatcher."""
    if settings.smtp_host and settings.smtp_username and settings.smtp_password:
        return SMTPDispatcher(
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            from_email=settings.smtp_from_email or settings.smtp_username,
            from_name=settings.smtp_from_name,
            use_tls=settings.smtp_use_tls,
        )
    return MockDispatcher()
