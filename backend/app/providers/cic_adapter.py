"""CIC Insurance Group - direct Kenyan underwriter.

Top-3 Kenyan insurer, strong in agricultural/climate microinsurance. No public API reference found. See docs/PROVIDER_LANDSCAPE.md for the full research and
docs/API_ACCESS_REQUEST_TEMPLATE.md for a ready-to-send outreach message.
"""

from app.providers.pending import PendingIntegrationAdapter


class CICAdapter(PendingIntegrationAdapter):
    PROVIDER_LABEL = "CIC Insurance Group"
    WHAT_IS_KNOWN = (
        "Top-3 Kenyan insurer, strong in agricultural/climate microinsurance. No public API reference found."
    )
