import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Category and status sets from spec §41.
TICKET_CATEGORIES = ("quote", "payment", "policy", "claim", "renewal", "technical", "general")
TICKET_STATUSES = ("open", "assigned", "in_progress", "waiting_customer", "resolved", "closed")


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reference: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"))
    category: Mapped[str] = mapped_column(String(30))
    subject: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(20), default="open")
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
