import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Identity, Index, Integer, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuditLog(Base):
    """One row per audited fact. APPEND-ONLY: the 0021 migration installs
    database triggers that refuse any UPDATE, DELETE or TRUNCATE, and no API
    endpoint edits or removes rows. There is deliberately no foreign key to
    users or customers so the trail outlives any account.

    kind:
      change  - a record was created / updated / deleted (written inside the
                same transaction as the change; carries before/after values)
      request - an HTTP request that changes data, or reads something
                sensitive, with its outcome (also records refused/failed
                attempts)
      event   - a named business or security event (sign-in, document opened,
                export, bulk delete…)
    """

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Strict ordering even when two rows share a timestamp.
    seq: Mapped[int] = mapped_column(BigInteger, Identity(), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    kind: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False)

    actor_type: Mapped[str] = mapped_column(String(10), nullable=False, default="system")
    actor_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    actor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(50), nullable=True)

    entity_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    related_customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # {"field": [old, new], ...} for change rows
    changes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    request_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    method: Mapped[str | None] = mapped_column(String(10), nullable=True)
    path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)

    __table_args__ = (Index("ix_audit_logs_entity", "entity_type", "entity_id"),)
