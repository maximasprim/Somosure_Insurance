"""Real email delivery via a standard SMTP account - a Gmail Workspace,
Microsoft 365, Zoho, or any other work email account with SMTP access
enabled. Deliberately provider-agnostic (plain SMTP, not a vendor
transactional-email API like SendGrid/SES) because a work email inbox is
what most small teams already have on hand, not a dedicated
transactional-email account.

Setup notes and the most common gotcha (an app-specific password, not
your normal login password, for accounts with 2FA enabled) live in
backend/.env.example next to the SMTP_* settings.
"""

import logging
from email.message import EmailMessage

import aiosmtplib

from app.notifications.base import DispatchResult, NotificationDispatcher

logger = logging.getLogger("somosure.notifications")


class SMTPDispatcher(NotificationDispatcher):
    is_mock = False

    def __init__(self, host: str, port: int, username: str, password: str, from_email: str, from_name: str, use_tls: bool):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.from_name = from_name
        self.use_tls = use_tls

    async def send_email(self, email: str, subject: str, body: str) -> DispatchResult:
        message = EmailMessage()
        message["From"] = f"{self.from_name} <{self.from_email}>" if self.from_name else self.from_email
        message["To"] = email
        message["Subject"] = subject
        message.set_content(body)

        try:
            await aiosmtplib.send(
                message,
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                start_tls=self.use_tls,
                timeout=15,
            )
            return DispatchResult(delivered=True, is_mock=False)
        except Exception as exc:  # noqa: BLE001 - a failed send must not crash the caller (e.g. forgot-password)
            logger.warning("SMTP send failed to=%s subject=%r error=%s", email, subject, exc)
            return DispatchResult(delivered=False, error=str(exc), is_mock=False)

    async def send_sms(self, phone: str, body: str) -> DispatchResult:
        raise NotImplementedError("SMTPDispatcher is email-only - use a separate dispatcher for SMS.")
