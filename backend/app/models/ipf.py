"""Bidii Credit IPF (insurance premium finance) pieces that sit around a financing
application: the loan officers who bring business in and the commission they earn,
the post-dated cheques held as security, and the record of an early settlement.

Kept in their own file (and their own tables) so nothing here changes the existing
financing tables beyond a few new nullable columns - see migration 0028.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# "linked": the client also has an auto/logbook loan with Bidii Credit, and the vehicle
# carries a tracker. "unlinked": IPF on its own - deposit plus post-dated cheques.
IPF_TYPES = ("unlinked", "linked")
CHEQUE_STATUSES = ("received", "banked", "bounced", "returned")
# awaiting_basis: the policy exists but Somosure's net commission on it hasn't been entered yet.
LOAN_OFFICER_COMMISSION_STATUSES = ("awaiting_basis", "pending", "approved", "paid", "cancelled")


class LoanOfficer(Base):
    """A Bidii Credit loan officer. Earns a share of Somosure's net commission on
    the policies they bring in through IPF, and has an optional monthly target."""

    __tablename__ = "loan_officers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str] = mapped_column(String(120))
    # The code a customer can quote when applying, so the sale is credited to this officer.
    staff_number: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(30))
    # Monthly sales target, in KES of premium financed. NULL = no target set.
    monthly_target: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class LoanOfficerCommission(Base):
    """What one loan officer earns from one financed policy. One per financing
    application. The rate that applied is copied onto the row so later changes to
    the setting never alter what was already earned."""

    __tablename__ = "loan_officer_commissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    loan_officer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("loan_officers.id"), index=True)
    financing_application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("financing_applications.id"), unique=True)
    policy_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("policies.id"))

    # Somosure's net commission on the policy - the amount the officer's share is taken
    # from. NULL until it is known (entered by finance, or worked out from the setting
    # "Somosure commission as % of premium").
    somosure_net_commission: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    rate_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    commission_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))

    status: Mapped[str] = mapped_column(String(16), default="awaiting_basis")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_by: Mapped[str | None] = mapped_column(String(100))
    payout_reference: Mapped[str | None] = mapped_column(String(100))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class FinancingCheque(Base):
    """A post-dated cheque the client handed over to cover one monthly repayment."""

    __tablename__ = "financing_cheques"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    financing_application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("financing_applications.id"), index=True)
    cheque_number: Mapped[str] = mapped_column(String(40))
    bank_name: Mapped[str] = mapped_column(String(80))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    cheque_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(12), default="received")
    notes: Mapped[str | None] = mapped_column(Text)

    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class FinancingSettlement(Base):
    """The record of a loan being cleared before its agreed term. One per agreement."""

    __tablename__ = "financing_settlements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agreement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("financing_agreements.id"), unique=True)
    financing_application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("financing_applications.id"), index=True)

    instalments_remaining: Mapped[int] = mapped_column(Integer)
    outstanding_principal: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    fee_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    fee_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    total_paid: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    # What the remaining instalments would have cost - shown so staff can see the saving.
    would_have_paid: Mapped[Decimal] = mapped_column(Numeric(14, 2))

    payment_reference: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)
    settled_by: Mapped[str | None] = mapped_column(String(100))
    settled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
