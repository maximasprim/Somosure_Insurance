"""Version history for imports: every committed import is kept as a numbered version together with the exact
workbook file that produced it, and any version can be put back.

How "put back" works
--------------------
An import is a pure function of (the workbook, what the ledger holds now). So putting version N back means
importing version N's own file again, in "revert" mode:

* rows whose values changed since N are set back to what N's file says;
* rows that did not exist in N are marked "missing from sheet" (the ledger never deletes), and the policy,
  payment, quote and application that posting made for them are removed again;
* the revert is itself recorded as a NEW version (history is never rewritten), so a revert can be reverted.

What a revert does not touch: sales recorded by hand in the system, staff follow-up notes, accepted date fixes
that still apply, name aliases, claims or documents added in the app, and platform policies. Automatic imports
are paused afterwards so the next scheduled pull does not simply undo the revert.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import get_storage
from app.models.sales_automation import ImportVersion
from app.models.sales_ledger import ImportBatch
from app.models.user import User

logger = logging.getLogger("somosure.sales_import.versions")

STORAGE_CATEGORY = "sales-workbooks"
SOURCES = ("manual", "google_sheet", "revert")


class VersionError(Exception):
    """A problem with a version request that the person can act on (shown as-is)."""


async def snapshot(
    db: AsyncSession, *, batch_id: uuid.UUID, data: bytes, sha: str, filename: str | None, source: str,
    period_from: str | None, period_to: str | None, counts: dict | None, user_id: str | None,
    reverted_to: uuid.UUID | None = None, note: str | None = None,
) -> ImportVersion:
    """Stores the workbook and records the version. Called inside the import's own transaction (and under its lock),
    so the version number is gapless and the row exists if and only if the import committed."""
    # The same file again (a revert, or an unchanged re-upload) reuses the copy already stored.
    path = await db.scalar(select(ImportVersion.storage_path).where(ImportVersion.file_sha256 == sha).limit(1))
    if not path:
        try:
            path = await get_storage().save(STORAGE_CATEGORY, _safe_name(filename), data)
        except Exception as exc:
            # Without the file a version could never be restored, so the import is refused rather than saved half-way.
            logger.exception("Could not store the workbook for the import history")
            raise VersionError(
                "The workbook could not be saved to storage, so nothing was imported. Try again in a few minutes; if it keeps "
                "happening, check the storage settings (Supabase) in the backend."
            ) from exc
    next_no = int(await db.scalar(select(func.coalesce(func.max(ImportVersion.version_no), 0))) or 0) + 1
    version = ImportVersion(
        id=uuid.uuid4(), version_no=next_no, batch_id=batch_id, source=source, filename=(filename or "")[:255] or None,
        file_sha256=sha, size_bytes=len(data), storage_path=path, period_from=period_from, period_to=period_to,
        counts=counts, note=note, reverted_to_version_id=reverted_to, created_by=uuid.UUID(user_id) if user_id else None,
    )
    db.add(version)
    await db.flush()
    return version


def _safe_name(filename: str | None) -> str:
    name = "".join(c if c.isalnum() or c in "._-" else "_" for c in (filename or "workbook.xlsx"))
    return name[-120:] or "workbook.xlsx"


async def latest(db: AsyncSession) -> ImportVersion | None:
    return await db.scalar(select(ImportVersion).order_by(ImportVersion.version_no.desc()).limit(1))


async def get(db: AsyncSession, version_id: uuid.UUID) -> ImportVersion:
    version = await db.get(ImportVersion, version_id)
    if version is None:
        raise LookupError("Version not found")
    return version


async def read_file(version: ImportVersion) -> bytes:
    try:
        return await get_storage().read(version.storage_path)
    except Exception as exc:  # storage backends raise different things; the cause is logged, the message is for staff
        logger.exception("Could not read stored workbook for version %s", version.version_no)
        raise VersionError(
            f"The workbook file for version {version.version_no} could not be read back from storage, so it cannot be restored."
        ) from exc


async def list_versions(db: AsyncSession, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
    newest = await latest(db)
    total = int(await db.scalar(select(func.count()).select_from(ImportVersion)) or 0)
    target = ImportVersion.__table__.alias("target")
    rows = (await db.execute(
        select(ImportVersion, User.full_name, target.c.version_no.label("reverted_to_no"))
        .outerjoin(User, User.id == ImportVersion.created_by)
        .outerjoin(target, target.c.id == ImportVersion.reverted_to_version_id)
        .order_by(ImportVersion.version_no.desc()).limit(limit).offset(offset)
    )).all()
    return {
        "total": total,
        "items": [serialise(v, created_by_name=name, reverted_to_no=rto, is_current=bool(newest and v.id == newest.id)) for v, name, rto in rows],
    }


def serialise(v: ImportVersion, *, created_by_name: str | None, reverted_to_no: int | None, is_current: bool) -> dict[str, Any]:
    return {
        "id": str(v.id), "version_no": v.version_no, "source": v.source, "filename": v.filename, "file_sha256": v.file_sha256,
        "size_bytes": v.size_bytes, "period_from": v.period_from, "period_to": v.period_to, "counts": v.counts, "note": v.note,
        "reverted_to_version_no": reverted_to_no, "created_by_name": created_by_name or ("Automatic import" if v.source == "google_sheet" else None),
        "created_at": v.created_at.isoformat() if v.created_at else None, "is_current": is_current,
    }


async def check_revertable(db: AsyncSession, version: ImportVersion) -> None:
    newest = await latest(db)
    if newest and newest.id == version.id:
        raise VersionError("That is already the current version - there is nothing to revert.")


async def batch_counts(db: AsyncSession, batch_id: uuid.UUID) -> dict | None:
    batch = await db.get(ImportBatch, batch_id)
    return batch.counts if batch else None
