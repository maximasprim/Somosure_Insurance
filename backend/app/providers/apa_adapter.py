"""APA Insurance - direct Kenyan underwriter.

Top-5 Kenyan insurer by government tender wins. No public API reference found - direct agency conversation likely required. See docs/PROVIDER_LANDSCAPE.md for the full research and
docs/API_ACCESS_REQUEST_TEMPLATE.md for a ready-to-send outreach message.
"""

from app.providers.pending import PendingIntegrationAdapter


class APAAdapter(PendingIntegrationAdapter):
    PROVIDER_LABEL = "APA Insurance"
    WHAT_IS_KNOWN = (
        "Top-5 Kenyan insurer by government tender wins. No public API reference found - direct agency conversation likely required."
    )
