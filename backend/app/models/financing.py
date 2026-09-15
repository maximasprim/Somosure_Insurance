import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Lifecycle from spec §14.
FINANCING_APPLICATION_STATUSES = ("eligibility_checked", "submitted", "approved", "rejected", "cancelled")
FINANCING_AGREEMENT_STATUSES = ("active", "completed", "defaulted", "cancelled")
INSTALLMENT_STATUSES = ("pending", "paid", "overdue", "waived")


class FinancingApplication(Base):
    """One request to finance a premium - kept entirely separate from the
    Policy/Application it funds, per spec §14's rule that financing must
    never alter insurance policy terms. Links to a Quote (the premium being
    financed), not a Policy, since eligibility is checked before a policy
    exists."""

    __tablename__ = "financing_applications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reference: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"))
    quote_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("quotes.id"))

    total_premium: Mapped[Numeric] = mapped_column(Numeric(14, 2))
    deposit_percentage: Mapped[Numeric] = mapped_column(Numeric(5, 2))
    deposit_amount: Mapped[Numeric] = mapped_column(Numeric(14, 2))
    financed_amount: Mapped[Numeric] = mapped_column(Numeric(14, 2))
    term_months: Mapped[int] = mapped_column(Integer)

    status: Mapped[str] = mapped_column(String(30), default="eligibility_checked")
    provider_reference: Mapped[str | None] = mapped_column(String(100))
    # Bidii Credit's own reference once submitted - populated by the adapter,
    # not fabricated here.
    rejection_reason: Mapped[str | None] = mapped_column(String(500))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class FinancingAgreement(Base):
    """The signed credit agreement once an application is approved -
    deliberately its own table (not a status on FinancingApplication) so
    it's unambiguous that this is a distinct credit obligation, separate
    from the insurance policy (spec §14: 'maintain clear separation
    between insurance obligation and credit obligation')."""

    __tablename__ = "financing_agreements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("financing_applications.id"), unique=True)
    policy_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("policies.id"), nullable=True)
    financed_amount: Mapped[Numeric] = mapped_column(Numeric(14, 2))
    term_months: Mapped[int] = mapped_column(Integer)
    monthly_installment: Mapped[Numeric] = mapped_column(Numeric(14, 2))
    status: Mapped[str] = mapped_column(String(20), default="active")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class FinancingInstallment(Base):
    __tablename__ = "financing_installments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agreement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("financing_agreements.id"))
    installment_number: Mapped[int] = mapped_column(Integer)
    due_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Numeric] = mapped_column(Numeric(14, 2))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
