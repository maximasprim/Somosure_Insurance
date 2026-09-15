"""mTek Services (Nairobi) - acquired by bolttech in December 2025.

Partners directly with GA Insurance, Sanlam, and Britam; offered a B2B
integration path for banks/MFIs prior to the acquisition. Post-acquisition,
new integration inquiries may route through bolttech's global partnerships
team rather than mTek's original Nairobi contact - confirm this in the
first outreach email (see docs/API_ACCESS_REQUEST_TEMPLATE.md).
"""

from app.providers.pending import PendingIntegrationAdapter


class MtekAdapter(PendingIntegrationAdapter):
    PROVIDER_LABEL = "mTek Services (bolttech)"
    WHAT_IS_KNOWN = (
        "mTek bridges GA Insurance, Sanlam, and Britam and was acquired by "
        "bolttech in Dec 2025 - confirm current integration contact before "
        "assuming mTek's original process still applies."
    )

    async def get_quotes_bulk(self, product_category, answers):
        """One mTek call should fan out across its confirmed underwriters
        (GA Insurance, Sanlam, Britam) - same multi-insurer pattern as
        Lami, at a smaller scale. Still raises until real API access
        exists - see docs/PROVIDER_LANDSCAPE.md."""
        raise self._not_ready("get_quotes_bulk (would fan out to GA Insurance, Sanlam, Britam)")
