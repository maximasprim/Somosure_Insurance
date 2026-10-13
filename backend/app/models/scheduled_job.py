from datetime import datetime

from sqlalchemy import DateTime, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ScheduledJob(Base):
    """One row per background job (renewal reminders, abandoned-quote recovery, ...).
    It is what lets several server instances share the work without running a job
    twice: a job is "claimed" by atomically moving locked_until forward, and only
    the instance whose update succeeded runs it. It also records when each job last
    ran and what it did, so staff can see that the scheduler is alive."""

    __tablename__ = "scheduled_jobs"

    name: Mapped[str] = mapped_column(String(60), primary_key=True)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    # While set and in the future, some instance is running this job.
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(20), nullable=True)  # ok | failed
    last_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
