"""Seed baseline roles, demo (mock) providers, and default automation
rules.

Run with: python -m app.db.seed
"""

import asyncio
import uuid

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.db.rate_card_seed_data import (
    AMACO_CLASSES,
    AMACO_PROVIDER_EXTENSIONS,
    AMACO_SOURCE,
    PIONEER_CLASSES,
    PIONEER_PROVIDER_EXTENSIONS,
    PIONEER_SOURCE,
    PROVIDERS as RATE_CARD_PROVIDERS,
)
from app.models.automation import AutomationRule
from app.models.provider import InsuranceProvider
from app.models.rate_card import RateCardExtension, RateCardTier, RateCardVehicleClass
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


_RATE_CARD_SOURCES = {"amaco": (AMACO_SOURCE, AMACO_CLASSES, AMACO_PROVIDER_EXTENSIONS),
                      "pioneer insurance kenya": (PIONEER_SOURCE, PIONEER_CLASSES, PIONEER_PROVIDER_EXTENSIONS)}


async def seed_rate_cards(db) -> tuple[int, int]:
    """Seeds AMACO and Pioneer Insurance Kenya as real (non-mock)
    providers backed by RateCardAdapter, plus every vehicle class, tier,
    and provider-wide extension transcribed from their rate cards (see
    app/db/rate_card_seed_data.py). Idempotent: safe to re-run, and never
    overwrites a class/tier an admin has since edited through
    /api/v1/admin/rate-cards - it only inserts rows that don't exist yet.
    """
    providers_created = 0
    classes_created = 0

    for provider_def in RATE_CARD_PROVIDERS:
        key = provider_def["key"]
        provider = await db.scalar(select(InsuranceProvider).where(InsuranceProvider.name == provider_def["name"]))
        if not provider:
            provider = InsuranceProvider(
                id=uuid.uuid4(),
                name=provider_def["name"],
                provider_type=provider_def["provider_type"],
                integration_mode="rate_card",
                status="active",
                supports_quote=True,
                integration_version="rate-card-1.0",
            )
            db.add(provider)
            await db.flush()
            providers_created += 1

        source_document, class_defs, provider_extensions = _RATE_CARD_SOURCES[key]

        for class_def in class_defs:
            existing_class = await db.scalar(
                select(RateCardVehicleClass).where(
                    RateCardVehicleClass.provider_id == provider.id,
                    RateCardVehicleClass.code == class_def["code"],
                )
            )
            if existing_class:
                continue  # never clobber an admin's edits on re-seed

            confidence = "needs_review" if key == "pioneer insurance kenya" else "verified"
            vehicle_class = RateCardVehicleClass(
                id=uuid.uuid4(),
                provider_id=provider.id,
                product_category="motor",
                code=class_def["code"],
                label=class_def["label"],
                min_sum_insured=class_def.get("min_sum_insured"),
                max_vehicle_age_years=class_def.get("max_vehicle_age_years"),
                source_document=source_document,
                data_confidence=confidence,
                notes=class_def.get("notes"),
            )
            db.add(vehicle_class)
            await db.flush()
            classes_created += 1

            for tier_def in class_def["tiers"]:
                db.add(RateCardTier(id=uuid.uuid4(), vehicle_class_id=vehicle_class.id, **tier_def))

            for ext_def in class_def.get("extensions", []):
                db.add(
                    RateCardExtension(
                        id=uuid.uuid4(),
                        provider_id=provider.id,
                        vehicle_class_id=vehicle_class.id,
                        **ext_def,
                    )
                )

        for ext_def in provider_extensions:
            existing_ext = await db.scalar(
                select(RateCardExtension).where(
                    RateCardExtension.provider_id == provider.id,
                    RateCardExtension.vehicle_class_id.is_(None),
                    RateCardExtension.code == ext_def["code"],
                )
            )
            if not existing_ext:
                db.add(RateCardExtension(id=uuid.uuid4(), provider_id=provider.id, vehicle_class_id=None, **ext_def))

    return providers_created, classes_created


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

        rate_card_providers_created, rate_card_classes_created = await seed_rate_cards(db)

        await db.commit()
        print(
            f"Seeded {len(ROLES)} roles, {len(DEMO_PROVIDERS)} demo providers, "
            f"1 demo aggregator, {len(REAL_PROVIDER_CANDIDATES)} real (pending-integration) providers, "
            f"{len(DEFAULT_RULES)} automation rules, and {rate_card_providers_created} rate-card provider(s) "
            f"with {rate_card_classes_created} vehicle classes (AMACO + Pioneer Insurance Kenya)."
        )


if __name__ == "__main__":
    asyncio.run(seed())
