"""NotificationDispatcher - mirrors the adapter pattern used everywhere
else in this codebase (InsuranceProviderAdapter, PaymentProviderAdapter,
CreditProviderAdapter): a real SMS/email provider is swappable behind
this interface, and the actions.py send_notification function calls it
after recording the Notification row, so the dispatch attempt itself is
logged and auditable regardless of whether it succeeds.

SMS has no real credentials configured by default (spec §51 - never
fabricate a delivery that didn't happen) - MockDispatcher logs what it
*would* send and returns success until real Africa's Talking credentials
are supplied (a Kenyan provider used widely for exactly this). Email has
a real implementation, SMTPDispatcher, that sends through a normal work
email account via SMTP - see backend/.env.example for the SMTP_* setup
notes; it also falls back to MockDispatcher until those are configured.
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
