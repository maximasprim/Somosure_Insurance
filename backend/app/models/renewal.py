import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Reminder cadence from spec §16.
REMINDER_DAYS_BEFORE_EXPIRY = (60, 30, 14, 7, 3, 1, 0)

RENEWAL_STATUSES = ("due", "contacted", "quoted", "paid", "renewed", "lost")


class Renewal(Base):
    """Tracks one policy's renewal lifecycle. Created the first time a
    reminder fires for that policy, not on a schedule - so there's exactly
    one Renewal per policy per expiry, and RenewalEvent captures every
    reminder sent against it."""

    __tablename__ = "renewals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("policies.id"), unique=True)
    due_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="due")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class RenewalEvent(Base):
    __tablename__ = "renewal_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    renewal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("renewals.id"))
    event_type: Mapped[str] = mapped_column(String(30))  # reminder_sent, contacted, quoted, renewed, lost
    days_before_expiry: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
