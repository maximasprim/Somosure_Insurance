import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

REFERRAL_STATUSES = ("pending", "converted", "rewarded", "expired")


class Referral(Base):
    """One referral code belonging to a customer, and (once used) the
    resulting new customer and reward state. Reward logic is deliberately
    configurable rather than hardcoded (spec §42: 'keep reward logic
    configurable') - reward_amount is set by whoever creates the referral
    program's rules, not computed here."""

    __tablename__ = "referrals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    referrer_customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"))
    referred_customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True)
    policy_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("policies.id"), nullable=True)
    # Set once the referred customer's first policy is issued - this is
    # what "conversion" means for this referral.

    status: Mapped[str] = mapped_column(String(20), default="pending")
    reward_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    reward_paid: Mapped[bool] = mapped_column(default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
