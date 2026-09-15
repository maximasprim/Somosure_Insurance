"""Jubilee Insurance - direct Kenyan underwriter.

Historically Kenya's #1 insurer by market share. Launched J-Force (2025), a paperless agent platform for policy issuance and transactions - but this appears agent-facing, not a public developer API. No public API reference found. See docs/PROVIDER_LANDSCAPE.md for the full research and
docs/API_ACCESS_REQUEST_TEMPLATE.md for a ready-to-send outreach message.
"""

from app.providers.pending import PendingIntegrationAdapter


class JubileeAdapter(PendingIntegrationAdapter):
    PROVIDER_LABEL = "Jubilee Insurance"
    WHAT_IS_KNOWN = (
        "Historically Kenya's #1 insurer by market share. Launched J-Force (2025), a paperless agent platform for policy issuance and transactions - but this appears agent-facing, not a public developer API. No public API reference found."
    )
