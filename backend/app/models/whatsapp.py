import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class WhatsAppConversation(Base):
    """One conversation thread per phone number. Linked to a Customer the
    same way a guest quote is - matched or created by phone number
    (app/services/whatsapp_service.py)."""

    __tablename__ = "whatsapp_conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True)
    state: Mapped[str] = mapped_column(String(30), default="idle")
    # idle | awaiting_category | awaiting_agent | ... - see whatsapp_service.py
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    assigned_agent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WhatsAppMessage(Base):
    __tablename__ = "whatsapp_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("whatsapp_conversations.id"))
    direction: Mapped[str] = mapped_column(String(10))  # inbound | outbound
    body: Mapped[str] = mapped_column(String(4000))
    provider_message_id: Mapped[str | None] = mapped_column(String(100))
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
