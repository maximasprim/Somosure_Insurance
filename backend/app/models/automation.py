import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Trigger events emitted around the codebase - kept as a plain string on
# the model (not an enum) so new events don't require a migration, but this
# is the authoritative list of what's actually emitted today:
#   policy.activated | renewal.reminder_due | quote.abandoned
KNOWN_TRIGGER_EVENTS = ("policy.activated", "renewal.reminder_due", "quote.abandoned")

# Actions a rule can take - each maps to one function in app/automation/actions.py.
KNOWN_ACTION_TYPES = ("send_notification", "create_task", "generate_sticker")


class AutomationRule(Base):
    """Admin-configurable event → condition → action rule (spec §27).

    conditions is a flat dict matched against the event's context by exact
    equality (e.g. {"category": "motor"}) - intentionally simple rather
    than a full expression language, so rules stay auditable and an admin
    screen can render them as plain form fields.
    """

    __tablename__ = "automation_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150))
    trigger_event: Mapped[str] = mapped_column(String(50))
    conditions: Mapped[dict] = mapped_column(JSON, default=dict)
    action_type: Mapped[str] = mapped_column(String(50))
    action_config: Mapped[dict] = mapped_column(JSON, default=dict)
    delay_seconds: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AutomationRun(Base):
    """One scheduled/executed firing of a rule against a specific entity -
    the audit trail spec §27 requires (conditions, delays, retries,
    failure handling all need something to log against)."""

    __tablename__ = "automation_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("automation_rules.id"))
    trigger_event: Mapped[str] = mapped_column(String(50))
    entity_type: Mapped[str] = mapped_column(String(30))  # policy, quote_request, lead, ...
    entity_id: Mapped[str] = mapped_column(String(50))
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
    # scheduled | executed | failed
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(String(1000))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
