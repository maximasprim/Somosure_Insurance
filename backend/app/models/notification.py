import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

NOTIFICATION_CHANNELS = ("email", "sms", "whatsapp", "in_app")


class Notification(Base):
    """A single notification instance - spec §26's event list (quote
    generated, payment successful, policy expiring, ...) all land here.

    No real email/SMS/WhatsApp provider is wired up yet (that's Phase 6's
    WhatsApp integration proper, and a Phase 10 concern for email/SMS
    providers) - every notification is recorded with status "sent" as a
    logged, retrievable record (visible at /api/v1/me/notifications) rather
    than actually dispatched. This keeps the event → rule → action engine
    genuinely exercised without silently pretending messages left the
    building.
    """

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"))
    channel: Mapped[str] = mapped_column(String(20))
    event_type: Mapped[str] = mapped_column(String(50))
    subject: Mapped[str | None] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    # pending | sent | failed - "sent" here means "recorded", not "delivered
    # by a real provider" until a real channel adapter exists.
    is_read: Mapped[bool] = mapped_column(default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
