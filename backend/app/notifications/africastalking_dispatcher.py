"""Africa's Talking - Kenya-based SMS/USSD/voice API provider, the
dominant choice for SMS delivery from Kenyan applications. Unlike the
insurers researched in docs/PROVIDER_LANDSCAPE.md, Africa's Talking has a
genuine self-serve developer signup - free sandbox credits, no business
partnership conversation required. Confirmed via their own site and
several independent developer guides (Sept 2026).

Not implemented for real here because no API key exists in this
environment - this is a credentials gap, not an access gap:

1. Register at https://account.africastalking.com/auth/register
2. Get a sandbox API key at https://account.africastalking.com/apps/sandbox/settings/key
3. Set AFRICASTALKING_API_KEY and AFRICASTALKING_USERNAME in backend/.env
4. Install the `africastalking` Python SDK and implement send_sms() below

Note: Kenyan SMS carries real compliance obligations once this goes
live - promotional SMS is restricted to 07:00-19:00 EAT, every recipient
needs documented opt-in, and every promotional message needs an
unsubscribe path. Transactional messages (payment confirmations, OTPs,
policy/claim status updates - everything this platform would actually
send) are exempt from the time restriction but should still respect
`Customer.consent_marketing` for anything non-transactional.
"""

from app.notifications.base import DispatchResult, NotificationDispatcher


class AfricasTalkingDispatcher(NotificationDispatcher):
    is_mock = False

    def __init__(self, api_key: str, username: str):
        self.api_key = api_key
        self.username = username

    async def send_sms(self, phone: str, body: str) -> DispatchResult:
        raise NotImplementedError(
            "AfricasTalkingDispatcher.send_sms() needs the `africastalking` SDK wired up "
            "against a real API key - see this file's module docstring for signup details."
        )

    async def send_email(self, email: str, subject: str, body: str) -> DispatchResult:
        raise NotImplementedError("Africa's Talking doesn't do email - use a separate email dispatcher for this method.")
