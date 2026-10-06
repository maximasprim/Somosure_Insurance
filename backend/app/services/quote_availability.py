"""Which product categories can we genuinely quote online right now?

A category is "live" when at least one ACTIVE provider whose adapter is a
real (non-mock) integration can price it - today that means the
rate-card brokers (AMACO, Pioneer) for motor. Categories that only have
the mock/demo insurers behind them (medical, life, travel, ...) are
reported as not available, so the frontend shows an honest "coming soon,
talk to an agent" message instead of demo numbers dressed up as quotes.

Nothing is hardcoded per category: when a real adapter or a rate card for
a new category is added, that category flips to live by itself. Set
ALLOW_DEMO_QUOTE_CATEGORIES=true in a demo/staging environment to count
the mock insurers too.
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.provider import InsuranceProvider
from app.providers.registry import get_adapter
from app.services.product_catalog import ALL_CATEGORIES, COMING_SOON_ALWAYS  # noqa: F401

logger = logging.getLogger("somosure.quote_availability")

# The catalogue lives in product_catalog.py (re-exported here for existing imports).


async def get_category_availability(db: AsyncSession) -> dict[str, dict]:
    providers = (await db.scalars(select(InsuranceProvider).where(InsuranceProvider.status == "active"))).all()

    live: set[str] = set()
    demo: set[str] = set()
    for provider in providers:
        try:
            adapter = get_adapter(provider)
            products = await adapter.get_products()
        except Exception:
            # A provider that can't even list its products (e.g. a pending
            # integration) simply doesn't contribute - never an error here.
            logger.debug("Provider %s could not list products", provider.name, exc_info=True)
            continue
        categories = {p.get("category") for p in products if p.get("category")}
        (demo if adapter.is_mock else live).update(categories)

    allow_demo = get_settings().allow_demo_quote_categories
    result: dict[str, dict] = {}
    for category in ALL_CATEGORIES:
        if category in COMING_SOON_ALWAYS:
            # Announced products with no pricing at all - never quotable, not even in demo mode.
            mode = "coming_soon"
        elif category in live:
            mode = "live"
        elif category in demo:
            mode = "demo" if allow_demo else "coming_soon"
        else:
            mode = "coming_soon"
        result[category] = {"available": mode in ("live", "demo"), "mode": mode}
    return result
