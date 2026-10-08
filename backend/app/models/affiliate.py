import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

AFFILIATE_SETTINGS_ID = "00000000-0000-0000-0000-0000000000a1"

RATE_TYPES = ("percent", "fixed")
COMMISSION_STATUSES = ("pending", "approved", "paid", "reversed", "rejected")


class AffiliateSettings(Base):
    """The program's one row of admin-editable configuration (exactly one row,
    id=AFFILIATE_SETTINGS_ID - get_affiliate_settings() creates it on first
    read, like the financing settings).

    Ships OFF with a 0% default rate: nobody earns anything until management
    switches the program on and sets a rate."""

    __tablename__ = "affiliate_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    program_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    default_rate_type: Mapped[str] = mapped_column(String(10), default="percent")
    default_rate_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))

    # Policies with a smaller premium than this earn nothing. NULL = no minimum.
    min_premium: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    # Most one policy can ever earn, whatever the rate. NULL = no cap.
    max_commission_per_policy: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)

    # "first_policy": only the referred customer's first policy earns.
    # "all_policies": every policy they buy within window_months of being referred.
    scope: Mapped[str] = mapped_column(String(20), default="first_policy")
    window_months: Mapped[int] = mapped_column(Integer, default=12)

    # False: new commissions wait for a person to approve them (recommended).
    auto_approve: Mapped[bool] = mapped_column(Boolean, default=False)
    # True: any customer may turn themselves into an affiliate (reusable code).
    allow_self_enrollment: Mapped[bool] = mapped_column(Boolean, default=False)

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Affiliate(Base):
    """A customer enrolled as an affiliate: they get a REUSABLE code (ordinary
    referral codes are single-use), a payout number and their own dashboard.
    Anyone can earn commission by referring; enrolling is for people who refer
    often. Suspending an affiliate stops new commissions for them."""

    __tablename__ = "affiliates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), unique=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(15), default="active")  # active | suspended
    payout_method: Mapped[str] = mapped_column(String(20), default="mpesa")
    payout_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AffiliateRateRule(Base):
    """One admin-set commission rate. Tied to a referrer and/or a product
    category and/or a date range - see app/services/affiliate_rates.py for how
    the best rule is chosen."""

    __tablename__ = "affiliate_rate_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    rate_type: Mapped[str] = mapped_column(String(10), default="percent")
    rate_value: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    max_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)

    affiliate_customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True
    )
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    starts_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    ends_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AffiliateCommission(Base):
    """What one referrer earned from one policy their referral bought.

    The rate that applied is COPIED onto the row, so changing rates later never
    alters what was already earned. One commission per policy at most."""

    __tablename__ = "affiliate_commissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    referral_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("referrals.id"))
    referrer_customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), index=True)
    referred_customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"))
    # Nullable + unique: one commission per policy, and the link is cleared
    # (not the commission deleted) if a provider and its policies are removed.
    policy_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("policies.id"), nullable=True, unique=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)

    premium: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    rate_type: Mapped[str] = mapped_column(String(10))
    rate_value: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    rate_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    commission_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))

    status: Mapped[str] = mapped_column(String(15), default="pending", index=True)
    status_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payout_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    payout_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
