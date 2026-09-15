"""ICEA Lion - direct Kenyan underwriter.

Major Kenyan insurer with strong claims-ratio performance. No public API reference found. See docs/PROVIDER_LANDSCAPE.md for the full research and
docs/API_ACCESS_REQUEST_TEMPLATE.md for a ready-to-send outreach message.
"""

from app.providers.pending import PendingIntegrationAdapter


class ICEALionAdapter(PendingIntegrationAdapter):
    PROVIDER_LABEL = "ICEA Lion"
    WHAT_IS_KNOWN = (
        "Major Kenyan insurer with strong claims-ratio performance. No public API reference found."
    )
