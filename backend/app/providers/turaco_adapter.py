"""Turaco - Nairobi-based embedded insurance API, focused on low-premium
health/life/accident products for MNO and fintech partners (e.g. its
M-KOPA integration passed 1M+ covered customers in 2025). API-first
posture makes them a plausible integration partner, though their product
focus (micro-premium, embedded) may fit Somosure's broader product range
less directly than Lami's.
"""

from app.providers.pending import PendingIntegrationAdapter


class TuracoAdapter(PendingIntegrationAdapter):
    PROVIDER_LABEL = "Turaco"
    WHAT_IS_KNOWN = (
        "Turaco is API-driven and embedded-insurance focused (health/life/"
        "accident, low premiums); no public API reference found - contact "
        "their partnerships team directly."
    )

    async def get_quotes_bulk(self, product_category, answers):
        """Turaco is more product-specific (low-premium health/life/
        accident) than a broad multi-insurer marketplace, so a bulk call
        here may return fewer underlying options than Lami or mTek - but
        the same fan-out shape applies if Turaco underwrites through
        multiple partners for a given product. Still raises until real
        API access exists - see docs/PROVIDER_LANDSCAPE.md."""
        raise self._not_ready("get_quotes_bulk")
