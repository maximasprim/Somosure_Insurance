"""Configurable rate-card engine (spec-extension, Sep 2026).

Real insurers/brokers don't all expose an API yet, but several have
published rate cards (PDF rating guides circulated to agents) with real,
current pricing. This module lets an admin type those rate cards into the
database - per provider, per product category, per vehicle/risk class - so
`RateCardAdapter` (app/providers/rate_card_adapter.py) can compute a real
premium from real published rates without needing a live API integration.

Nothing here is mock data: every row traces back to a specific rate card
document (`source_document` on RateCardVehicleClass). Where a source
document was hard to parse cleanly, `data_confidence="needs_review"` says
so explicitly rather than presenting a guess as certain - the same
honesty rule the rest of this codebase applies to `is_mock`.

Adding a new broker later is a data operation, not a code change: create
an InsuranceProvider row with integration_mode="rate_card", then use the
admin API (app/api/v1/admin_rate_cards.py) to add its classes/tiers/
extensions/excesses. The registry (app/providers/registry.py) only needs
one new line mapping the provider's name to RateCardAdapter.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RateCardVehicleClass(Base):
    """One insurable risk class for one provider, e.g. "AMACO's Motor
    Private (070)" or "Pioneer's PSV Taxi - Online". `code` is a canonical,
    provider-agnostic identifier (see docs/RATE_CARDS.md for the full
    list) - the same code means the same kind of risk across every
    provider, so the quote engine can ask every rate-card provider for
    "motor_private" and get back each one's own numbers for it.

    Despite the name, `product_category` is NOT hardcoded to motor - it's
    a free string matching InsuranceProduct.category (motor, medical,
    life, travel, home, business, personal_accident, ...) so a future
    broker's medical or travel rate card slots in without a schema change.
    Only motor is seeded today because that's the only rate card data
    supplied so far.
    """

    __tablename__ = "rate_card_vehicle_classes"
    __table_args__ = (UniqueConstraint("provider_id", "code", name="uq_rate_card_class_provider_code"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("insurance_providers.id"), nullable=False)

    product_category: Mapped[str] = mapped_column(String(30), default="motor")
    code: Mapped[str] = mapped_column(String(60), nullable=False)
    # canonical code, e.g. "motor_private", "psv_taxi" - see docs/RATE_CARDS.md
    label: Mapped[str] = mapped_column(String(150))
    # human-readable name as the provider's document calls it, e.g.
    # "Motor Private (070)"

    min_sum_insured: Mapped[Numeric | None] = mapped_column(Numeric(14, 2))
    max_vehicle_age_years: Mapped[int | None] = mapped_column()

    source_document: Mapped[str | None] = mapped_column(String(500))
    # e.g. "AMACO Rating Guide - 2026 Revised Motor Rates (circulated 2 Jul 2026)"
    data_confidence: Mapped[str] = mapped_column(String(20), default="verified")
    # verified | needs_review - "needs_review" means the source document
    # didn't extract/parse cleanly; surfaced to staff and in quote metadata
    # rather than silently treated as certain.
    notes: Mapped[str | None] = mapped_column(Text)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class RateCardTier(Base):
    """One priced band within a vehicle class, e.g. "AMACO Motor Private,
    Comprehensive, sum insured 1.0M-2.5M -> 3.5%, min premium 30,000".

    `band_unit` says what `min_value`/`max_value` measure - the same class
    can have sum-insured-banded comprehensive tiers and tonnage- or
    passenger-banded TPO tiers, or no banding at all (a single flat
    amount). `max_value` of NULL means "and above".
    """

    __tablename__ = "rate_card_tiers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vehicle_class_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rate_card_vehicle_classes.id"), nullable=False)

    cover_type: Mapped[str] = mapped_column(String(20))  # comprehensive | tpo
    band_unit: Mapped[str] = mapped_column(String(20), default="sum_insured")
    # sum_insured | tonnes | passengers | subtype | none
    subtype_key: Mapped[str | None] = mapped_column(String(50))
    # used only when band_unit="subtype", e.g. "prime_mover" | "trailer" | "fleet"
    # - lets one class carry several distinct flat TPO options that aren't
    # banded by a number at all (spec: AMACO's general cartage TPO table).

    min_value: Mapped[Numeric | None] = mapped_column(Numeric(14, 2))
    max_value: Mapped[Numeric | None] = mapped_column(Numeric(14, 2))
    # inclusive band [min_value, max_value]; NULL max_value = unbounded above

    rate_percent: Mapped[Numeric | None] = mapped_column(Numeric(6, 3))
    # applied to the sum insured when set
    flat_amount: Mapped[Numeric | None] = mapped_column(Numeric(14, 2))
    # used instead of rate_percent for fixed-amount tiers (most TPO tiers)
    min_premium: Mapped[Numeric | None] = mapped_column(Numeric(14, 2))
    # floor applied after rate_percent * sum_insured is computed

    label: Mapped[str | None] = mapped_column(String(150))
    # free text describing the band as the source document phrased it,
    # e.g. "1,500,000 - 2,499,999" or "9 - 15 tonnes"
    tier_order: Mapped[int] = mapped_column(default=0)


class RateCardExtension(Base):
    """An optional add-on benefit priced on top of the base premium, e.g.
    PVT, Excess Protector, Courtesy Car, Windscreen, PLL, COMESA Yellow
    Card. `vehicle_class_id` NULL means the extension is a provider-wide
    default available to any of that provider's classes unless a
    class-specific row overrides it.
    """

    __tablename__ = "rate_card_extensions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("insurance_providers.id"), nullable=False)
    vehicle_class_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("rate_card_vehicle_classes.id"))

    code: Mapped[str] = mapped_column(String(50))
    # pvt | excess_protector | courtesy_car | windscreen | pll | comesa_yellow_card | ...
    label: Mapped[str] = mapped_column(String(150))
    basis: Mapped[str] = mapped_column(String(30), default="percent_of_sum_insured")
    # percent_of_sum_insured | flat | per_person
    rate_percent: Mapped[Numeric | None] = mapped_column(Numeric(6, 3))
    flat_amount: Mapped[Numeric | None] = mapped_column(Numeric(14, 2))
    min_amount: Mapped[Numeric | None] = mapped_column(Numeric(14, 2))
    notes: Mapped[str | None] = mapped_column(Text)


class RateCardExcess(Base):
    """A claim-time excess (deductible) disclosed at quote time so the
    comparison table can show it, e.g. "Own Damage - 2.5% of sum insured,
    min KES 15,000". Informational for pricing (doesn't change the
    premium) but material to what the customer is actually comparing.
    """

    __tablename__ = "rate_card_excesses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("insurance_providers.id"), nullable=False)
    vehicle_class_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rate_card_vehicle_classes.id"), nullable=False)

    peril: Mapped[str] = mapped_column(String(50))
    # own_damage | theft_with_tracking | theft_with_antitheft | theft_without_antitheft
    # | third_party_property_damage | young_inexperienced_driver
    basis: Mapped[str] = mapped_column(String(30), default="percent_of_sum_insured")
    rate_percent: Mapped[Numeric | None] = mapped_column(Numeric(6, 3))
    flat_amount: Mapped[Numeric | None] = mapped_column(Numeric(14, 2))
    min_amount: Mapped[Numeric | None] = mapped_column(Numeric(14, 2))
    label: Mapped[str | None] = mapped_column(String(150))