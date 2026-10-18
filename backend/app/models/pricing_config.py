"""Admin-editable pricing rules that sit beside the existing financing and renewal
features, so no number is hard-coded:

  * FinancingRateTier - the monthly interest rate for a loan of a given size and term;
  * AnniversarySettings / ShortPeriodScale / CustomerAnniversary - renewing all of a
    customer's covers on one anniversary date, and what a short-period cover costs.

All new tables (migration 0029); existing tables are not changed.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

ANNIVERSARY_SETTINGS_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a1")


class FinancingRateTier(Base):
    """"For a loan from min_amount (inclusive) up to max_amount (exclusive), over
    min_term..max_term months (inclusive), the monthly rate is X." A blank max means
    no upper limit. See rate_tier_math.py for how overlapping tiers are resolved."""

    __tablename__ = "financing_rate_tiers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    label: Mapped[str] = mapped_column(String(80))
    # all | individual | corporate
    applies_to: Mapped[str] = mapped_column(String(12), default="all", server_default="all")
    min_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"), server_default="0")
    max_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    min_term_months: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    max_term_months: Mapped[int | None] = mapped_column(Integer)
    interest_rate_monthly: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AnniversarySettings(Base):
    """The one row of anniversary-alignment configuration (see anniversary_math.py)."""

    __tablename__ = "anniversary_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=ANNIVERSARY_SETTINGS_ID)
    # Master switch. Off hides the alignment from the renewals screen; nothing is deleted.
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    # pro_rata_daily | short_period_scale
    method: Mapped[str] = mapped_column(String(24), default="pro_rata_daily", server_default="pro_rata_daily")
    year_basis_days: Mapped[int] = mapped_column(Integer, default=365, server_default="365")
    # A short period never costs less than this % of the annual premium.
    minimum_premium_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"), server_default="0")
    # A stub shorter than this many days is flagged as "very short".
    min_stub_days: Mapped[int] = mapped_column(Integer, default=30, server_default="30")
    # Longest cover term (days) the insurers allow. 366 = a year at most (the default), so
    # a very short stub is never stretched; raise it if an insurer allows longer.
    max_term_days: Mapped[int] = mapped_column(Integer, default=366, server_default="366")

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by: Mapped[str | None] = mapped_column(String(100))


class ShortPeriodScale(Base):
    """One band of an insurer's short-period table: "cover for up to `up_to_days` days
    costs `percent_of_annual`% of the annual premium". provider_id NULL = the default
    table used for any provider without a table of its own."""

    __tablename__ = "short_period_scales"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("insurance_providers.id"), index=True)
    up_to_days: Mapped[int] = mapped_column(Integer)
    percent_of_annual: Mapped[Decimal] = mapped_column(Numeric(5, 2))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CustomerAnniversary(Base):
    """The common anniversary agreed for a customer. Only its month and day matter."""

    __tablename__ = "customer_anniversaries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), unique=True)
    anniversary_date: Mapped[date] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    set_by: Mapped[str | None] = mapped_column(String(100))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
