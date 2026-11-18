"""Automatic weekly import from a Google Sheet, and the version history of every import.

Three small tables:

* `sales_import_settings`  one row: which sheet to pull, how often, whether it is switched on or paused.
* `import_versions`        one row per committed import (manual upload, scheduled pull, or a revert). The exact
                           workbook file is kept in document storage, so any version can be re-applied later.
* `sales_import_runs`      one row per automatic attempt, including the ones that changed nothing or failed, so a
                           silent failure is visible on the screen.

They sit beside the ledger tables (models/sales_ledger.py) and change none of them.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SalesImportSettings(Base):
    """The single settings row (id is always 1)."""

    __tablename__ = "sales_import_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_sales_import_settings_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=1)
    sheet_url: Mapped[str | None] = mapped_column(Text)
    sheet_id: Mapped[str | None] = mapped_column(String(120))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    frequency: Mapped[str] = mapped_column(String(10), default="weekly", server_default="weekly")  # daily | weekly | monthly
    weekday: Mapped[int] = mapped_column(Integer, default=0, server_default="0")  # 0 = Monday (weekly)
    day_of_month: Mapped[int] = mapped_column(Integer, default=1, server_default="1")  # 1-28 (monthly)
    hour: Mapped[int] = mapped_column(Integer, default=6, server_default="6")  # 0-23, Nairobi time
    period_from: Mapped[str | None] = mapped_column(String(7))  # "2025-01": same meaning as the Import tab
    period_to: Mapped[str | None] = mapped_column(String(7))
    auto_post: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")  # also post new rows into the system
    # Set when automatic imports are stopped on purpose (a revert). Nothing runs until someone resumes.
    paused_reason: Mapped[str | None] = mapped_column(Text)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[str | None] = mapped_column(String(20))  # imported | no_changes | failed
    last_message: Mapped[str | None] = mapped_column(Text)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ImportVersion(Base):
    """One committed import, with the exact workbook that produced it."""

    __tablename__ = "import_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version_no: Mapped[int] = mapped_column(Integer, unique=True)  # 1, 2, 3 ... assigned under the import lock
    batch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("import_batches.id"), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(20))  # manual | google_sheet | revert
    filename: Mapped[str | None] = mapped_column(String(255))
    file_sha256: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    storage_path: Mapped[str] = mapped_column(String(500))
    period_from: Mapped[str | None] = mapped_column(String(7))
    period_to: Mapped[str | None] = mapped_column(String(7))
    counts: Mapped[dict | None] = mapped_column(JSON)
    note: Mapped[str | None] = mapped_column(Text)
    reverted_to_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("import_versions.id"), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SalesImportRun(Base):
    """An automatic (or 'run now') attempt to pull the Google Sheet, whatever came of it."""

    __tablename__ = "sales_import_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trigger: Mapped[str] = mapped_column(String(20))  # scheduled | run_now
    status: Mapped[str] = mapped_column(String(20))  # imported | no_changes | failed
    message: Mapped[str | None] = mapped_column(Text)
    version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("import_versions.id"), nullable=True)
    counts: Mapped[dict | None] = mapped_column(JSON)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
