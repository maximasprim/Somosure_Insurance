"""Read-only access to the audit trail.

There is deliberately no endpoint that edits or deletes an entry (and the
database refuses it too). Reading the trail is limited to super_admin and
management; exporting it is itself recorded in the trail.
"""

import csv
import io
import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.context import record_event
from app.core.database import get_db
from app.core.security import require_roles
from app.models.audit import AuditLog
from app.schemas.audit import AuditEntryOut, AuditFacetsOut, AuditPageOut

router = APIRouter(
    prefix="/api/v1/admin/audit",
    tags=["admin-audit"],
    dependencies=[Depends(require_roles("super_admin", "management"))],
)

EXPORT_CAP = 50_000


def _filters(
    kind: str | None,
    actor: str | None,
    actor_user_id: str | None,
    entity_type: str | None,
    entity_id: str | None,
    customer_id: str | None,
    action: str | None,
    q: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    failed_only: bool,
    exclude_kind: str | None = None,
) -> list:
    conds = []
    if kind:
        conds.append(AuditLog.kind == kind)
    if exclude_kind:
        conds.append(AuditLog.kind != exclude_kind)
    if actor_user_id:
        conds.append(AuditLog.actor_user_id == actor_user_id)
    if actor:
        like = f"%{actor.strip()}%"
        conds.append(or_(AuditLog.actor_name.ilike(like), AuditLog.actor_email.ilike(like)))
    if entity_type:
        conds.append(AuditLog.entity_type == entity_type)
    if entity_id:
        conds.append(AuditLog.entity_id == entity_id)
    if customer_id:
        conds.append(AuditLog.related_customer_id == customer_id)
    if action:
        conds.append(AuditLog.action == action)
    if q:
        like = f"%{q.strip()}%"
        conds.append(
            or_(
                AuditLog.summary.ilike(like),
                AuditLog.entity_label.ilike(like),
                AuditLog.reason.ilike(like),
                AuditLog.actor_name.ilike(like),
                AuditLog.path.ilike(like),
            )
        )
    if date_from:
        conds.append(AuditLog.occurred_at >= date_from)
    if date_to:
        conds.append(AuditLog.occurred_at <= date_to)
    if failed_only:
        conds.append(AuditLog.status_code >= 400)
    return conds


@router.get("", response_model=AuditPageOut)
async def list_audit(
    kind: str | None = Query(None, pattern="^(change|request|event)$"),
    actor: str | None = None,
    actor_user_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    customer_id: str | None = None,
    action: str | None = None,
    q: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    failed_only: bool = False,
    exclude_kind: str | None = Query(None, pattern="^(change|request|event)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    conds = _filters(
        kind, actor, actor_user_id, entity_type, entity_id, customer_id, action, q, date_from, date_to, failed_only, exclude_kind
    )
    total = await db.scalar(select(func.count()).select_from(AuditLog).where(*conds)) or 0
    rows = (
        await db.scalars(
            select(AuditLog).where(*conds).order_by(AuditLog.occurred_at.desc(), AuditLog.seq.desc()).limit(limit).offset(offset)
        )
    ).all()
    return AuditPageOut(items=[AuditEntryOut.model_validate(r) for r in rows], total=total, limit=limit, offset=offset)


@router.get("/facets", response_model=AuditFacetsOut)
async def audit_facets(db: AsyncSession = Depends(get_db)):
    """Values for the filter dropdowns."""
    types = (await db.scalars(select(AuditLog.entity_type).where(AuditLog.entity_type.is_not(None)).distinct())).all()
    actions = (
        await db.scalars(select(AuditLog.action).where(AuditLog.kind != "request").distinct().limit(200))
    ).all()
    return AuditFacetsOut(entity_types=sorted(types), actions=sorted(actions))


def _csv_safe(value) -> str:
    """Stops a spreadsheet from treating exported text as a formula."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


@router.get("/export.csv")
async def export_audit(
    kind: str | None = Query(None, pattern="^(change|request|event)$"),
    actor: str | None = None,
    actor_user_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    customer_id: str | None = None,
    action: str | None = None,
    q: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    failed_only: bool = False,
    db: AsyncSession = Depends(get_db),
):
    conds = _filters(kind, actor, actor_user_id, entity_type, entity_id, customer_id, action, q, date_from, date_to, failed_only)
    rows = (
        await db.scalars(
            select(AuditLog).where(*conds).order_by(AuditLog.occurred_at.desc(), AuditLog.seq.desc()).limit(EXPORT_CAP)
        )
    ).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["time_utc", "kind", "actor_type", "actor_name", "actor_email", "actor_role", "action", "entity_type",
         "entity_id", "entity_label", "summary", "reason", "status_code", "ip", "request_id", "changes"]
    )
    for r in rows:
        writer.writerow(
            [_csv_safe(v) for v in (
                r.occurred_at.isoformat(), r.kind, r.actor_type, r.actor_name, r.actor_email, r.actor_role, r.action,
                r.entity_type, r.entity_id, r.entity_label, r.summary, r.reason, r.status_code, r.ip, r.request_id,
                json.dumps(r.changes, default=str) if r.changes else "",
            )]
        )
    record_event("audit.exported", summary=f"Exported {len(rows)} audit entries to CSV", rows=len(rows))
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="audit-trail.csv"'},
    )


@router.get("/{entry_id}", response_model=AuditEntryOut)
async def get_audit_entry(entry_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    entry = await db.get(AuditLog, entry_id)
    if not entry:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Audit entry not found")
    return entry
