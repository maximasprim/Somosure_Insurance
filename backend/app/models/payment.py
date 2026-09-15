import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Status set from spec §13.
PAYMENT_STATUSES = ("initiated", "pending", "successful", "failed", "reversed", "refunded")


class Payment(Base):
    """One payment intent - e.g. 'pay for this application'. Holds the
    amount owed and the outcome; the individual provider round-trips
    (STK push sent, callback received, ...) live in PaymentTransaction."""

    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reference: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    # e.g. SOM-PAY-2026-000123

    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"))
    application_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("applications.id"), nullable=True)
    policy_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("policies.id"), nullable=True)

    amount: Mapped[Numeric] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="KES")
    method: Mapped[str] = mapped_column(String(20))  # mpesa | card | bank_transfer
    status: Mapped[str] = mapped_column(String(20), default="initiated")

    payer_phone: Mapped[str | None] = mapped_column(String(30))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PaymentTransaction(Base):
    """Every provider round-trip against a Payment - the STK push
    initiation, each callback received, manual reconciliation notes.
    Kept separate from Payment so the audit trail survives even if the
    same payment intent takes multiple provider attempts."""

    __tablename__ = "payment_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("payments.id"))

    provider: Mapped[str] = mapped_column(String(30))  # mpesa_daraja, mock_mpesa, stripe, ...
    provider_transaction_id: Mapped[str | None] = mapped_column(String(100))
    # e.g. M-Pesa CheckoutRequestID / MpesaReceiptNumber

    direction: Mapped[str] = mapped_column(String(10))  # outbound (STK push) | inbound (callback)
    status: Mapped[str] = mapped_column(String(20))
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    # Full provider payload, kept for dispute resolution and audit (spec §29)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
