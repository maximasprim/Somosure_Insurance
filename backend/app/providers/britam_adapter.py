"""Britam - direct Kenyan underwriter.

One of Kenya's 'big three' underwriters (~4M microinsurance customers, 2024). Runs bespoke embedded-insurance integrations (M-TIBA, Telkom, Airtel, Little Cab) under the 'Britam Connect' branding, but no public developer API portal was found. Likely requires a direct agency/partner conversation. See docs/PROVIDER_LANDSCAPE.md for the full research and
docs/API_ACCESS_REQUEST_TEMPLATE.md for a ready-to-send outreach message.
"""

from app.providers.pending import PendingIntegrationAdapter


class BritamAdapter(PendingIntegrationAdapter):
    PROVIDER_LABEL = "Britam"
    WHAT_IS_KNOWN = (
        "One of Kenya's 'big three' underwriters (~4M microinsurance customers, 2024). Runs bespoke embedded-insurance integrations (M-TIBA, Telkom, Airtel, Little Cab) under the 'Britam Connect' branding, but no public developer API portal was found. Likely requires a direct agency/partner conversation."
    )
