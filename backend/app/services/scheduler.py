"""Background jobs: the existing scan functions, run on a timer.

Jobs (each is an existing function that is safe to run repeatedly):
  renewals            scan_renewals              reminders at 60/30/14/7/3/1/0 days
  abandoned_quotes    scan_abandoned_quotes      recovery nudge after 4 hours
  automations         run_due_automations        executes scheduled automation actions
  payments_reconcile  reconcile_pending_payments settles M-Pesa payments with a lost callback

Three ways to trigger them, all safe to combine:
  1. the in-process loop (SCHEDULER_ENABLED=true) started with the web app;
  2. POST /api/v1/internal/cron/run from an outside scheduler (CRON_SECRET);
  3. the existing buttons in Admin -> Automation.

A job is "claimed" with an atomic database update (see ScheduledJob), so even with
several server instances, or a timer AND an outside cron firing together, each job
runs once per interval.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.automation.engine import run_due_automations
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.models.scheduled_job import ScheduledJob
from app.services.payment_service import reconcile_pending_payments
from app.services.quote_recovery_service import scan_abandoned_quotes
from app.services.renewal_service import scan_renewals

logger = logging.getLogger("somosure.scheduler")


@dataclass(frozen=True)
class Job:
    name: str
    run: Callable[[AsyncSession], Awaitable[dict]]
    every: timedelta  # how often it should run
    lease: timedelta  # how long a run may take before another instance may take over


JOBS: tuple[Job, ...] = (
    Job("payments_reconcile", reconcile_pending_payments, every=timedelta(minutes=2), lease=timedelta(minutes=5)),
    Job("automations", run_due_automations, every=timedelta(minutes=5), lease=timedelta(minutes=10)),
    Job("abandoned_quotes", scan_abandoned_quotes, every=timedelta(minutes=30), lease=timedelta(minutes=10)),
    # Reminders are idempotent per policy per day-bucket, so running every few hours
    # is safe and means a restart or an outage on the "right" day doesn't skip a reminder.
    Job("renewals", scan_renewals, every=timedelta(hours=6), lease=timedelta(minutes=15)),
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _claim(db: AsyncSession, job: Job, *, force: bool) -> bool:
    """Atomically take the right to run `job` now. True for exactly one caller."""
    now = _now()
    await db.execute(pg_insert(ScheduledJob).values(name=job.name, next_run_at=now).on_conflict_do_nothing(index_elements=["name"]))
    conditions = [ScheduledJob.name == job.name, or_(ScheduledJob.locked_until.is_(None), ScheduledJob.locked_until < now)]
    if not force:
        conditions.append(ScheduledJob.next_run_at <= now)
    result = await db.execute(
        update(ScheduledJob)
        .where(*conditions)
        .values(locked_until=now + job.lease, last_started_at=now)
        .returning(ScheduledJob.name)
    )
    claimed = result.first() is not None
    await db.commit()
    return claimed


async def _finish(db: AsyncSession, job: Job, status: str, result: dict) -> None:
    now = _now()
    await db.execute(
        update(ScheduledJob)
        .where(ScheduledJob.name == job.name)
        .values(
            locked_until=None,
            next_run_at=now + job.every,
            last_finished_at=now,
            last_status=status,
            last_result=result,
        )
    )
    await db.commit()


async def run_jobs(only: list[str] | None = None, *, force: bool = False) -> dict[str, dict]:
    """Runs every job that is due (or the named ones). Returns what happened per job:
    {"status": "ok" | "failed" | "skipped", ...}. Never raises - one failing job does
    not stop the others."""
    report: dict[str, dict] = {}
    for job in JOBS:
        if only and job.name not in only:
            continue
        try:
            async with AsyncSessionLocal() as db:
                if not await _claim(db, job, force=force):
                    report[job.name] = {"status": "skipped", "reason": "not due or already running"}
                    continue
            try:
                async with AsyncSessionLocal() as db:
                    outcome = await job.run(db)
                async with AsyncSessionLocal() as db:
                    await _finish(db, job, "ok", outcome if isinstance(outcome, dict) else {"result": str(outcome)})
                report[job.name] = {"status": "ok", "result": outcome}
            except Exception as exc:
                logger.exception("Scheduled job %s failed", job.name)
                async with AsyncSessionLocal() as db:
                    await _finish(db, job, "failed", {"error": str(exc)[:500]})
                report[job.name] = {"status": "failed", "error": str(exc)[:200]}
        except Exception:
            logger.exception("Scheduler could not process job %s", job.name)
            report[job.name] = {"status": "failed", "error": "scheduler error"}
    return report


async def scheduler_loop() -> None:
    """The in-process timer. Wakes every SCHEDULER_TICK_SECONDS and runs what is due."""
    tick = max(get_settings().scheduler_tick_seconds, 10)
    logger.info("Scheduler started (checking every %ss)", tick)
    while True:
        try:
            report = await run_jobs()
            ran = {k: v for k, v in report.items() if v["status"] != "skipped"}
            if ran:
                logger.info("Scheduler ran: %s", ran)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Scheduler tick failed")
        await asyncio.sleep(tick)
