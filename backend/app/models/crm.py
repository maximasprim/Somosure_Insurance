import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Pipeline stages from spec §18.
LEAD_STAGES = ("new", "contacted", "qualified", "quote", "negotiation", "won", "lost")

# Source list from spec §18.
LEAD_SOURCES = (
    "website",
    "whatsapp",
    "facebook",
    "instagram",
    "google",
    "referral",
    "agent",
    "partner",
    "walk_in",
    "campaign",
)


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"))
    stage: Mapped[str] = mapped_column(String(20), default="new")
    source: Mapped[str] = mapped_column(String(20), default="website")
    product_interest: Mapped[str | None] = mapped_column(String(30))
    # motor, medical, ... - what they're shopping for, if known

    assigned_agent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Links back to the quote/application that generated or advanced this
    # lead, so an agent can jump straight to the customer's actual activity
    # instead of just seeing a name and a stage.
    quote_request_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("quote_requests.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class LeadActivity(Base):
    """Every touch on a lead - stage change, call, note, follow-up. The
    'activities' timeline required by spec §18's customer/lead profile."""

    __tablename__ = "lead_activities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id"))
    activity_type: Mapped[str] = mapped_column(String(30))
    # stage_changed, call, note, follow_up_scheduled, quote_sent, ...
    notes: Mapped[str | None] = mapped_column(String(2000))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Communication(Base):
    """A logged customer-facing message - SMS/email/WhatsApp/call summary -
    kept separate from LeadActivity so it survives even if a lead is later
    deleted/merged, and so Phase 6's WhatsApp integration has a single
    table to write into regardless of which lead or policy it relates to."""

    __tablename__ = "communications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"))
    channel: Mapped[str] = mapped_column(String(20))  # email, sms, whatsapp, call, in_app
    direction: Mapped[str] = mapped_column(String(10))  # inbound, outbound
    subject: Mapped[str | None] = mapped_column(String(255))
    body: Mapped[str | None] = mapped_column(String(4000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Task(Base):
    """A staff to-do, optionally tied to a lead - e.g. 'call back
    tomorrow', created manually by an agent for now; Phase 6's automation
    engine will also create these from rules."""

    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255))
    lead_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=True)
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | done
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
