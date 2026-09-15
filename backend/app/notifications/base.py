"""NotificationDispatcher - mirrors the adapter pattern used everywhere
else in this codebase (InsuranceProviderAdapter, PaymentProviderAdapter,
CreditProviderAdapter): a real SMS/email provider is swappable behind
this interface, and the actions.py send_notification function calls it
after recording the Notification row, so the dispatch attempt itself is
logged and auditable regardless of whether it succeeds.

No real SMS/email credentials exist in this codebase (spec §51 - never
fabricate a delivery that didn't happen). MockDispatcher logs what it
*would* send and returns success; a real dispatcher (e.g. Africa's
Talking for SMS - a Kenyan provider used widely for exactly this - or
SendGrid/SES for email) plugs in by implementing this same interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DispatchResult:
    delivered: bool
    provider_message_id: str | None = None
    error: str | None = None
    is_mock: bool = True


class NotificationDispatcher(ABC):
    is_mock: bool = True

    @abstractmethod
    async def send_sms(self, phone: str, body: str) -> DispatchResult: ...

    @abstractmethod
    async def send_email(self, email: str, subject: str, body: str) -> DispatchResult: ...
