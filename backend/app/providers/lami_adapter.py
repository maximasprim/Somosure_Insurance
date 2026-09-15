"""Lami Technologies - Nairobi-based insurance-as-a-service API platform.

Highest-priority outreach target (see docs/PROVIDER_LANDSCAPE.md): a single
integration reportedly bridges ~25 Kenyan insurers, and Lami's own
positioning (banks, platforms, and businesses embedding insurance via
their API) matches Somosure's use case directly. Existing enterprise
integrations reportedly include Stanbic Bank Kenya and Jumia.

No public API reference was found during research - Lami's technical
docs appear to be partner-gated, which is normal for a B2B2C platform.
Reaching out (docs/API_ACCESS_REQUEST_TEMPLATE.md) is the next step, not
guessing at endpoint shapes.
"""

from app.providers.pending import PendingIntegrationAdapter


class LamiAdapter(PendingIntegrationAdapter):
    PROVIDER_LABEL = "Lami Technologies"
    WHAT_IS_KNOWN = (
        "Lami is a Kenyan insurance-as-a-service API aggregator connecting to "
        "~25 underwriters; no public API reference is available - request "
        "partner/developer access directly."
    )

    async def get_quotes_bulk(self, product_category, answers):
        """This is the method that matters most for Lami: one real call
        here should return a NormalizedQuote per underlying insurer Lami
        offers this product through (reportedly ~25 insurers total),
        letting a single integration populate a full comparison table
        instead of one row. Still raises until real API access exists -
        see docs/PROVIDER_LANDSCAPE.md."""
        raise self._not_ready("get_quotes_bulk (would fan out to ~25 underlying insurers per call)")
