"""Seed baseline roles, demo (mock) providers, and default automation
rules.

Run with: python -m app.db.seed
"""

import asyncio
import uuid

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.automation import AutomationRule
from app.models.provider import InsuranceProvider
from app.models.user import Role

ROLES = [
    "super_admin",
    "management",
    "operations",
    "underwriter",
    "sales_agent",
    "claims_officer",
    "finance_officer",
    "customer_support",
    "marketing",
    "partner",
    "customer",
]

# Named "Demo Insurer A/B" rather than real brand names - these are MOCK
# providers for development. Real providers are added by an admin once
# actual integration details exist (spec §51).
DEMO_PROVIDERS = ["Demo Insurer A", "Demo Insurer B", "Demo Insurer C"]

# Demonstrates the aggregator fan-out architecture (docs/PROVIDER_LANDSCAPE.md)
# end-to-end without needing Lami/mTek/Turaco's real credentials: one
# active provider row, backed by MockAggregatorProvider, that returns
# quotes "from" three named demo underwriters in a single get_quotes_bulk()
# call - proving multiple comparison rows can come from one provider
# record before any real aggregator is connected.
DEMO_AGGREGATOR = "Demo Aggregator (mock)"

# Real, named Kenyan insurers and aggregators researched for Phase 7 (see
# docs/PROVIDER_LANDSCAPE.md). Seeded as inactive placeholder rows with no
# API credentials - each has a corresponding adapter under app/providers/
# that raises NotImplementedError until real API access is granted.
# provider_type is "insurer" for direct underwriters, "aggregator" for
# platforms that bridge multiple underwriters.
REAL_PROVIDER_CANDIDATES = [
    ("Lami Technologies", "aggregator"),
    ("mTek Services", "aggregator"),
    ("Turaco", "aggregator"),
    ("Britam", "insurer"),
    ("Jubilee Insurance", "insurer"),
    ("APA Insurance", "insurer"),
    ("CIC Insurance Group", "insurer"),
    ("ICEA Lion", "insurer"),
    ("Old Mutual Kenya", "insurer"),
]

# Default automation rules (spec §27). Editable/deactivatable from
# /api/v1/admin/automation/rules once seeded - these are starting points,
# not hardcoded behavior.
DEFAULT_RULES = [
    {
        "name": "Generate sticker on motor policy activation",
        "trigger_event": "policy.activated",
        "conditions": {"category": "motor"},
        "action_type": "generate_sticker",
        "action_config": {},
        "delay_seconds": 0,
    },
    {
        "name": "Notify customer their policy is active",
        "trigger_event": "policy.activated",
        "conditions": {},
        "action_type": "send_notification",
        "action_config": {
            "channel": "sms",
            "subject": "Policy activated",
            "body_template": "Your policy {policy_number} is now active. Welcome to Somosure!",
        },
        "delay_seconds": 0,
    },
    {
        "name": "Send renewal reminder",
        "trigger_event": "renewal.reminder_due",
        "conditions": {},
        "action_type": "send_notification",
        "action_config": {
            "channel": "sms",
            "subject": "Renewal reminder",
            "body_template": "Your policy {policy_number} is due for renewal in {days_remaining} days.",
        },
        "delay_seconds": 0,
    },
    {
        "name": "Recover abandoned quote",
        "trigger_event": "quote.abandoned",
        "conditions": {},
        "action_type": "send_notification",
        "action_config": {
            "channel": "sms",
            "subject": "Complete your quote",
            "body_template": "You started a {category} insurance quote ({quote_reference}). Continue where you left off - we saved it for you.",
        },
        "delay_seconds": 0,
    },
]


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        for role_name in ROLES:
            existing = await db.scalar(select(Role).where(Role.name == role_name))
            if not existing:
                db.add(Role(id=uuid.uuid4(), name=role_name))

        for provider_name in DEMO_PROVIDERS:
            existing = await db.scalar(
                select(InsuranceProvider).where(InsuranceProvider.name == provider_name)
            )
            if not existing:
                db.add(
                    InsuranceProvider(
                        id=uuid.uuid4(),
                        name=provider_name,
                        provider_type="insurer",
                        integration_mode="mock",
                        status="active",
                        supports_quote=True,
                        integration_version="mock-0.1",
                    )
                )

        existing_aggregator = await db.scalar(
            select(InsuranceProvider).where(InsuranceProvider.name == DEMO_AGGREGATOR)
        )
        if not existing_aggregator:
            db.add(
                InsuranceProvider(
                    id=uuid.uuid4(),
                    name=DEMO_AGGREGATOR,
                    provider_type="aggregator",
                    integration_mode="mock",
                    status="active",
                    supports_quote=True,
                    integration_version="mock-0.1",
                )
            )

        for provider_name, provider_type in REAL_PROVIDER_CANDIDATES:
            existing = await db.scalar(
                select(InsuranceProvider).where(InsuranceProvider.name == provider_name)
            )
            if not existing:
                db.add(
                    InsuranceProvider(
                        id=uuid.uuid4(),
                        name=provider_name,
                        provider_type=provider_type,
                        integration_mode="rest",
                        status="inactive",
                        # status stays inactive - quote_service only queries
                        # active providers, so these never get called until
                        # an admin flips status after the real adapter is built.
                        supports_quote=False,
                        integration_version="pending",
                    )
                )

        for rule in DEFAULT_RULES:
            existing = await db.scalar(select(AutomationRule).where(AutomationRule.name == rule["name"]))
            if not existing:
                db.add(AutomationRule(id=uuid.uuid4(), is_active=True, **rule))

        await db.commit()
        print(
            f"Seeded {len(ROLES)} roles, {len(DEMO_PROVIDERS)} demo providers, "
            f"1 demo aggregator, {len(REAL_PROVIDER_CANDIDATES)} real (pending-integration) providers, "
            f"and {len(DEFAULT_RULES)} automation rules."
        )


if __name__ == "__main__":
    asyncio.run(seed())
