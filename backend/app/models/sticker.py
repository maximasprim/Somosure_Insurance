import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Status set from spec §12, in issuance order.
STICKER_STATUSES = (
    "pending",
    "validated",
    "payment_confirmed",
    "generating",
    "generated",
    "ready_for_collection",
    "dispatched",
    "delivered",
    "cancelled",
    "replaced",
)


class Sticker(Base):
    __tablename__ = "stickers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reference: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    # e.g. SOM-STK-2026-000123
    policy_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("policies.id"))
    status: Mapped[str] = mapped_column(String(30), default="pending")
    qr_payload: Mapped[str | None] = mapped_column(String(500))
    # Encodes reference + policy_number only - never PII - for a real QR
    # generator to render client-side. No QR image is generated server-side
    # yet; this is the data contract, not a rendering pipeline.

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class StickerEvent(Base):
    """Append-only issuance history - the audit trail and fraud-prevention
    control spec §12 requires (every status transition, who made it)."""

    __tablename__ = "sticker_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sticker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stickers.id"))
    from_status: Mapped[str | None] = mapped_column(String(30))
    to_status: Mapped[str] = mapped_column(String(30))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
