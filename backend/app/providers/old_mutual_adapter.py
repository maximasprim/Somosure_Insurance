"""Old Mutual Kenya - direct Kenyan underwriter.

Major insurer (formerly UAP Holdings). No public API reference found. See docs/PROVIDER_LANDSCAPE.md for the full research and
docs/API_ACCESS_REQUEST_TEMPLATE.md for a ready-to-send outreach message.
"""

from app.providers.pending import PendingIntegrationAdapter


class OldMutualAdapter(PendingIntegrationAdapter):
    PROVIDER_LABEL = "Old Mutual Kenya"
    WHAT_IS_KNOWN = (
        "Major insurer (formerly UAP Holdings). No public API reference found."
    )
