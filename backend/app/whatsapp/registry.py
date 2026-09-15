from app.core.config import get_settings
from app.whatsapp.base import WhatsAppAdapter
from app.whatsapp.mock_adapter import MockWhatsAppAdapter

settings = get_settings()


def get_whatsapp_adapter() -> WhatsAppAdapter:
    # A real GraphAPIWhatsAppAdapter gets registered here once a WABA ID
    # and access token exist - see docs/WHATSAPP.md.
    return MockWhatsAppAdapter()
