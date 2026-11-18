"""Automatic import from a Google Sheet, and reverting to an earlier import.

Entry points
------------
* `run_due_sales_import(db)`   the scheduler job (every few minutes): does nothing unless an import is due.
* `run_sync(db, trigger=...)`  pull the sheet and import it now ("Run now" button, or the scheduler).
* `revert_preview` / `revert`  see, then do, a return to an earlier version (see versions.py).
* `get_settings_row`, `update_settings`, `resume`, `settings_view`   the settings form.

An automatic run never imports a sheet that has not changed: identical file, or a file that would change nothing,
is logged as "no changes" and creates no version, so the history only holds real changes.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sales_automation import SalesImportRun, SalesImportSettings
from app.services.sales_import import google_sheet, schedule, versions
from app.services.sales_import.google_sheet import SheetFetchError, SheetLinkError
from app.services.sales_import.parser import WorkbookError

logger = logging.getLogger("somosure.sales_import.auto")

RETRY_AFTER = timedelta(hours=6)  # after a failed pull: try again sooner than the next scheduled slot
MAX_RETRIES = 3  # ... this many times in a row, then wait for the normal slot


class SettingsError(ValueError):
    """The settings cannot be saved as given (shown as-is)."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------------------- settings


async def get_settings_row(db: AsyncSession) -> SalesImportSettings:
    await db.execute(pg_insert(SalesImportSettings).values(id=1).on_conflict_do_nothing(index_elements=["id"]))
    row = await db.get(SalesImportSettings, 1)
    assert row is not None
    return row


def settings_view(row: SalesImportSettings) -> dict[str, Any]:
    return {
        "sheet_url": row.sheet_url, "enabled": row.enabled, "frequency": row.frequency, "weekday": row.weekday,
        "day_of_month": row.day_of_month, "hour": row.hour, "period_from": row.period_from, "period_to": row.period_to,
        "auto_post": row.auto_post, "paused_reason": row.paused_reason,
        "schedule_text": schedule.describe(row.frequency, row.weekday, row.day_of_month, row.hour),
        "next_run_at": row.next_run_at.isoformat() if row.next_run_at else None,
        "last_run_at": row.last_run_at.isoformat() if row.last_run_at else None,
        "last_status": row.last_status, "last_message": row.last_message, "consecutive_failures": row.consecutive_failures,
    }


def _next_slot(row: SalesImportSettings, now: datetime | None = None) -> datetime:
    return schedule.next_run_after(now or _now(), frequency=row.frequency, weekday=row.weekday, day_of_month=row.day_of_month, hour=row.hour)


async def update_settings(db: AsyncSession, data: dict[str, Any], *, user_id: str | None) -> SalesImportSettings:
    row = await get_settings_row(db)
    before = (row.enabled, row.frequency, row.weekday, row.day_of_month, row.hour, row.sheet_id)

    link = (data.get("sheet_url") or "").strip()
    if link:
        try:
            sheet_id = google_sheet.parse_sheet_link(link)
        except SheetLinkError as exc:
            raise SettingsError(str(exc))
        if sheet_id != row.sheet_id:
            row.consecutive_failures, row.last_status, row.last_message = 0, None, None
        row.sheet_url, row.sheet_id = link, sheet_id
    else:
        row.sheet_url = row.sheet_id = None

    for field in ("enabled", "frequency", "weekday", "day_of_month", "hour", "period_from", "period_to", "auto_post"):
        if field in data:
            setattr(row, field, data[field])
    if row.period_from and row.period_to and row.period_to < row.period_from:
        raise SettingsError("The end of the period is before its start.")
    if row.enabled and not row.sheet_id:
        raise SettingsError("Add the Google Sheet link before switching automatic import on.")
    if not row.enabled or row.paused_reason:
        row.next_run_at = None  # off or on hold: nothing is scheduled
    elif row.next_run_at is None or before != (row.enabled, row.frequency, row.weekday, row.day_of_month, row.hour, row.sheet_id):
        row.next_run_at = _next_slot(row)
    row.updated_by = uuid.UUID(user_id) if user_id else None
    await db.commit()
    return row


async def resume(db: AsyncSession, *, user_id: str | None) -> SalesImportSettings:
    row = await get_settings_row(db)
    row.paused_reason = None
    row.consecutive_failures = 0
    row.next_run_at = _next_slot(row) if row.enabled and row.sheet_id else None
    row.updated_by = uuid.UUID(user_id) if user_id else None
    await db.commit()
    return row


# ---------------------------------------------------------------------------------------- pulling the sheet


def _has_changes(report: dict[str, Any]) -> bool:
    return any(c.get(k, 0) for c in report["counts"].values() for k in ("new", "updated", "missing"))


def _summary(report: dict[str, Any]) -> str:
    s = report["counts"]["sales"]
    return f"{s['new']} new, {s['updated']} changed, {s['missing']} no longer in the sheet"


async def run_sync(db: AsyncSession, *, trigger: str, user_id: str | None = None) -> dict[str, Any]:
    """Pulls the sheet and imports it if it changed. Never raises for a problem with the sheet or the file: the
    outcome is recorded (run log + settings) and returned. `trigger` is "scheduled" or "run_now"."""
    from app.services.sales_import.service import run_import  # late: service imports versions, this imports service

    row = await get_settings_row(db)
    if not row.sheet_id:
        raise SettingsError("Add the Google Sheet link first.")
    sheet_id, period_from, period_to, auto_post = row.sheet_id, row.period_from, row.period_to, row.auto_post
    run_id = uuid.uuid4()  # kept as a plain value: a rollback below expires the ORM object, and reading it would hit the database
    db.add(SalesImportRun(id=run_id, trigger=trigger, status="failed", started_at=_now()))
    await db.commit()

    status, message, counts, version_id = "failed", "", None, None
    try:
        data = await google_sheet.fetch_workbook(sheet_id)
        newest = await versions.latest(db)
        filename = f"google-sheet-{_now().date().isoformat()}.xlsx"
        if newest and newest.file_sha256 == hashlib.sha256(data).hexdigest():
            status, message = "no_changes", "The sheet is identical to the last import."
        else:
            preview = await run_import(db, filename=filename, data=data, dry_run=True, user_id=None, period_from=period_from, period_to=period_to)
            if not _has_changes(preview):
                status, message, counts = "no_changes", "Nothing in the sheet has changed since the last import.", preview["counts"]
            else:
                report = await run_import(
                    db, filename=filename, data=data, dry_run=False, user_id=user_id, period_from=period_from, period_to=period_to,
                    post=auto_post, source="google_sheet",
                )
                status, counts = "imported", report["counts"]
                version_id = uuid.UUID(report["version_id"])
                message = f"Imported as version {report['version_no']}: {_summary(report)}."
                if report.get("posting", {}) and report["posting"].get("error"):
                    message += " Posting to the system did not complete - run it from the Post to system tab."
    except (SheetFetchError, WorkbookError, versions.VersionError) as exc:
        await db.rollback()
        message = str(exc)
    except Exception:
        await db.rollback()
        logger.exception("Automatic sales import failed unexpectedly")
        message = "Something went wrong while importing. The details are in the server log; nothing was changed."

    now = _now()
    run = await db.get(SalesImportRun, run_id)
    run.status, run.message, run.counts, run.version_id, run.finished_at = status, message, counts, version_id, now
    row = await get_settings_row(db)
    row.last_run_at, row.last_status, row.last_message = now, status, message
    if status == "failed":
        row.consecutive_failures += 1
    else:
        row.consecutive_failures = 0
    if trigger == "scheduled" and row.enabled and not row.paused_reason:
        retry = status == "failed" and row.consecutive_failures <= MAX_RETRIES
        row.next_run_at = now + RETRY_AFTER if retry else _next_slot(row, now)
    await db.commit()
    return {"status": status, "message": message, "version_id": str(version_id) if version_id else None}


async def run_due_sales_import(db: AsyncSession) -> dict[str, Any]:
    """The scheduler job. Cheap when nothing is due."""
    row = await get_settings_row(db)
    await db.commit()
    if not row.enabled or not row.sheet_id:
        return {"status": "idle", "reason": "automatic import is off"}
    if row.paused_reason:
        return {"status": "idle", "reason": "paused"}
    if row.next_run_at is None:
        row.next_run_at = _next_slot(row)
        await db.commit()
        return {"status": "idle", "reason": "scheduled"}
    if row.next_run_at > _now():
        return {"status": "idle", "reason": "not due yet"}
    return await run_sync(db, trigger="scheduled")


async def list_runs(db: AsyncSession, limit: int = 30) -> list[dict[str, Any]]:
    rows = (await db.execute(select(SalesImportRun).order_by(SalesImportRun.started_at.desc()).limit(limit))).scalars().all()
    return [
        {"id": str(r.id), "trigger": r.trigger, "status": r.status, "message": r.message, "counts": r.counts,
         "started_at": r.started_at.isoformat() if r.started_at else None, "finished_at": r.finished_at.isoformat() if r.finished_at else None}
        for r in rows
    ]


# ---------------------------------------------------------------------------------------- reverting


async def revert_preview(db: AsyncSession, version_id: uuid.UUID) -> dict[str, Any]:
    """What putting this version back would do. Changes nothing."""
    from app.services.sales_import.service import run_import

    version = await versions.get(db, version_id)
    await versions.check_revertable(db, version)
    data = await versions.read_file(version)
    report = await run_import(db, filename=version.filename, data=data, dry_run=True, user_id=None, period_from=version.period_from, period_to=version.period_to)
    settings = await get_settings_row(db)
    return {
        "version_no": version.version_no, "created_at": version.created_at.isoformat() if version.created_at else None,
        "counts": report["counts"], "changes_total": report["changes_total"], "changes": report["changes"][:25],
        "missing_total": report["missing_total"], "missing": report["missing"][:25],
        "posted_to_remove": report["missing_posted"],
        "will_pause_automation": bool(settings.enabled and not settings.paused_reason),
    }


async def revert(db: AsyncSession, version_id: uuid.UUID, *, user_id: str | None, reason: str | None) -> dict[str, Any]:
    from app.services.sales_import.service import run_import

    version = await versions.get(db, version_id)
    await versions.check_revertable(db, version)
    data = await versions.read_file(version)
    report = await run_import(
        db, filename=version.filename, data=data, dry_run=False, user_id=user_id, period_from=version.period_from, period_to=version.period_to,
        post=False, source="revert", reverted_to=version.id, unpost_missing=True, note=(reason or "").strip() or None,
    )
    settings = await get_settings_row(db)
    paused = False
    if settings.enabled:
        settings.paused_reason = (
            f"Paused after going back to version {version.version_no}. The next automatic import would bring the sheet's "
            "current contents back, so it is on hold. Resume once the Google Sheet matches what you restored, or when you "
            "want the sheet's current contents imported again."
        )
        settings.next_run_at = None
        paused = True
    await db.commit()
    return {"version_no": report["version_no"], "restored": version.version_no, "counts": report["counts"], "posting": report.get("posting"), "automation_paused": paused}
