import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, JSON, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Full lifecycle from spec §10.
POLICY_STATUSES = (
    "quote",
    "application",
    "under_review",
    "approved",
    "payment_pending",
    "active",
    "expired",
    "cancelled",
    "renewal_pending",
    "renewed",
    "rejected",
)


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    # Provider's own number where they issue one, else our own SOM-POL-... reference

    application_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("applications.id"))
    provider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("insurance_providers.id"))
    product_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("insurance_products.id"))
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"))

    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    premium: Mapped[Numeric] = mapped_column(Numeric(14, 2))
    payment_status: Mapped[str] = mapped_column(String(20), default="pending")
    status: Mapped[str] = mapped_column(String(30), default="active")

    agent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    source: Mapped[str | None] = mapped_column(String(50))
    commission: Mapped[Numeric | None] = mapped_column(Numeric(14, 2))

    is_mock: Mapped[bool] = mapped_column(default=True)
    # Mirrors the quote's is_mock flag - never present a mock policy as real.

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PolicyDocument(Base):
    __tablename__ = "policy_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("policies.id"))
    document_type: Mapped[str] = mapped_column(String(50))
    # policy_document, certificate, receipt
    storage_path: Mapped[str] = mapped_column(String(500))
    is_mock: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PolicyEvent(Base):
    """Append-only history of every status change on a policy - the
    'complete history of every policy event' required by spec §10."""

    __tablename__ = "policy_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("policies.id"))
    event_type: Mapped[str] = mapped_column(String(50))
    # status_changed, document_generated, payment_recorded, ...
    from_status: Mapped[str | None] = mapped_column(String(30))
    to_status: Mapped[str | None] = mapped_column(String(30))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
