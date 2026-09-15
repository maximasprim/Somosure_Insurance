import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, JSON, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Status set from spec §15.
CLAIM_STATUSES = (
    "reported",
    "documents_required",
    "submitted",
    "under_review",
    "insurer_review",
    "approved",
    "rejected",
    "settled",
    "closed",
)


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reference: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    # e.g. SOM-CLM-2026-000123
    policy_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("policies.id"))
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"))

    incident_date: Mapped[date] = mapped_column(Date)
    incident_description: Mapped[str] = mapped_column(String(2000))
    incident_location: Mapped[str | None] = mapped_column(String(255))

    status: Mapped[str] = mapped_column(String(30), default="reported")

    # Where the insurer's own API supports claims (spec §15's "where
    # insurer APIs are available, integrate claims status"), this holds
    # their reference. Null for MockProvider and every pending real
    # adapter today - staff-assisted processing is the only path until a
    # real adapter implements submit_claim/get_claim_status for real.
    provider_reference: Mapped[str | None] = mapped_column(String(100))
    provider_metadata: Mapped[dict] = mapped_column(JSON, default=dict)

    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ClaimDocument(Base):
    __tablename__ = "claim_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("claims.id"))
    document_type: Mapped[str] = mapped_column(String(50))
    # incident_photo, police_abstract, medical_report, repair_quote, ...
    storage_path: Mapped[str] = mapped_column(String(500))
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column()
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClaimEvent(Base):
    """Append-only status/activity history - the audit trail every claim
    status change and staff action leaves behind."""

    __tablename__ = "claim_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("claims.id"))
    event_type: Mapped[str] = mapped_column(String(30))  # status_changed, note_added, document_uploaded, ...
    from_status: Mapped[str | None] = mapped_column(String(30))
    to_status: Mapped[str | None] = mapped_column(String(30))
    notes: Mapped[str | None] = mapped_column(String(2000))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
