"""Database side of the weekly-report import.

run_import() is the one entry point. With dry_run=True it reads the file, works out exactly what
the upload would add / change / mark missing, and returns that - writing nothing. With
dry_run=False it does the same and then applies it in one transaction.

Writes use bulk statements (one round trip per few hundred rows, not per row), which also means
they bypass the per-row change capture of the audit trail on purpose: an import would otherwise
write thousands of audit lines. Instead the import records ONE audit event with the counts, and
the batch keeps the list of every changed field (import_batches.summary).
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, insert, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.context import record_event
from app.models.policy import Policy
from app.models.provider import InsuranceProvider
from app.models.sales_ledger import ImportAlias, ImportBatch, IpfRemittance, LegacyClaim, SalesEntry
from app.services.sales_import import posting, unified
from app.services.sales_import.cleaners import MONTH_NAMES, StaffResolver, norm_text, resolve_underwriter
from app.services.sales_import.export import build_cleaned_workbook
from app.services.sales_import.parser import WorkbookError, parse_workbook
from app.services.sales_import.period import apply_period, in_period, parse_period, row_period
from app.services.sales_import.pipeline import resolve_workbook
from app.services.sales_import.reconcile import reconcile
from app.services.sales_import.sync import (
    CLAIM_TRACKED,
    FIX_RESOLVES,
    IPF_TRACKED,
    SALES_TRACKED,
    SyncPlan,
    best_sales_match,
    level_of,
    plan_sync,
)

__all__ = ["WorkbookError", "run_import"]

logger = logging.getLogger("somosure.sales_import")

MAX_UPLOAD_BYTES = 15 * 1024 * 1024
IMPORT_LOCK_KEY = 7_201_001  # pg advisory lock: one import at a time
CHUNK = 400
MAX_ISSUES_SHOWN = 500
MAX_CHANGES_SHOWN = 200


# --------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    return value


def _chunks(items: list, size: int = CHUNK):
    for i in range(0, len(items), size):
        yield items[i:i + size]


async def _load_aliases(db: AsyncSession) -> tuple[dict[str, str], dict[str, tuple[str | None, str | None]]]:
    rows = (await db.scalars(select(ImportAlias))).all()
    underwriters = {a.alias_key: a.canonical for a in rows if a.kind == "underwriter" and a.canonical}
    staff = {a.alias_key: (a.canonical, a.branch) for a in rows if a.kind == "staff"}
    return underwriters, staff


async def _provider_index(db: AsyncSession) -> dict[str, uuid.UUID]:
    rows = (await db.execute(select(InsuranceProvider.id, InsuranceProvider.name))).all()
    return {norm_text(name): pid for pid, name in rows}


def _match_provider(underwriter: str | None, index: dict[str, uuid.UUID]) -> uuid.UUID | None:
    if not underwriter:
        return None
    key = norm_text(underwriter)
    if key in index:
        return index[key]
    for name, provider_id in index.items():
        if name.startswith(key + " ") or key.startswith(name + " "):
            return provider_id
    return None


async def _existing(db: AsyncSession, model, fields: list[str]) -> list[dict[str, Any]]:
    columns = {"id", "natural_key", "status", *fields}
    if hasattr(model, "fallback_key"):
        columns.add("fallback_key")
    if hasattr(model, "overrides"):
        columns.add("overrides")
    if hasattr(model, "origin"):
        columns.add("origin")
    for extra in ("sheet_year", "period_year", "client_name", "policy_number", "sheet_name", "sheet_row"):
        if hasattr(model, extra):
            columns.add(extra)
    result = await db.execute(select(*[getattr(model, c) for c in sorted(columns)]))
    return [dict(row) for row in result.mappings().all()]


def _counts(plan: SyncPlan) -> dict[str, int]:
    return {
        "new": len(plan.inserts), "updated": len(plan.updated), "unchanged": len(plan.unchanged),
        "restored": len(plan.restored), "missing": len(plan.missing_ids),
        "total": len(plan.inserts) + len(plan.matched),
    }


# --------------------------------------------------------------------------------------
# the import
# --------------------------------------------------------------------------------------


async def run_import(db: AsyncSession, *, filename: str | None, data: bytes, dry_run: bool, user_id: str | None,
                     period_from: str | None = None, period_to: str | None = None, post: bool = False) -> dict[str, Any]:
    try:
        start, end = parse_period(period_from), parse_period(period_to)
    except ValueError as exc:
        raise WorkbookError(str(exc))
    if start and end and end < start:
        raise WorkbookError("The end of the period is before its start.")
    if not data:
        raise WorkbookError("The uploaded file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise WorkbookError("That file is too large - the limit is 15MB.")

    if not dry_run:
        # Serialises imports so two uploads can't both decide "this row is new".
        await db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": IMPORT_LOCK_KEY})

    sha = hashlib.sha256(data).hexdigest()
    pw = await asyncio.to_thread(parse_workbook, data)
    skipped = apply_period(pw, start, end)
    uw_aliases, staff_aliases = await _load_aliases(db)
    rw = await asyncio.to_thread(resolve_workbook, pw, uw_aliases, staff_aliases)
    recon = reconcile(pw.blocks, pw.sales)

    providers = await _provider_index(db)
    for rows in (rw.sales, rw.claims, rw.ipf):
        for row in rows:
            row["provider_id"] = _match_provider(row.get("underwriter"), providers)

    years = {kind: {s.year for s in pw.sheets if s.kind == kind} for kind in ("sales", "claims", "ipf")}
    sales_existing = await _existing(db, SalesEntry, SALES_TRACKED)
    claims_existing = await _existing(db, LegacyClaim, CLAIM_TRACKED)
    ipf_existing = await _existing(db, IpfRemittance, IPF_TRACKED)

    # Only rows inside the chosen period (and in a sheet that was uploaded) can be judged "missing".
    def sales_scope(e):
        if e.get("origin") == "manual":
            return False  # recorded in the system: it may legitimately not be in the sheet
        return e["sheet_year"] in years["sales"] and in_period(e["period_year"], e["period_month"], start, end)

    def claims_scope(e):
        return e["period_year"] in years["claims"] and in_period(*row_period(e.get("date_reported"), e["period_year"]), start, end)

    def ipf_scope(e):
        return e["period_year"] in years["ipf"] and in_period(*row_period(e.get("date_paid"), e["period_year"]), start, end)

    plans = {
        "sales": plan_sync(rw.sales, sales_existing, tracked=SALES_TRACKED, year_field="sheet_year", uploaded_years=years["sales"],
                           use_fallback=True, in_scope=sales_scope, overrides=True),
        "claims": plan_sync(rw.claims, claims_existing, tracked=CLAIM_TRACKED, year_field="period_year", uploaded_years=years["claims"], in_scope=claims_scope),
        "ipf": plan_sync(rw.ipf, ipf_existing, tracked=IPF_TRACKED, year_field="period_year", uploaded_years=years["ipf"], in_scope=ipf_scope),
    }
    existing_by_id = {
        "sales": {e["id"]: e for e in sales_existing},
        "claims": {e["id"]: e for e in claims_existing},
        "ipf": {e["id"]: e for e in ipf_existing},
    }

    report = _build_report(
        filename=filename, sha=sha, dry_run=dry_run, pw=pw, rw=rw, recon=recon, plans=plans, existing_by_id=existing_by_id,
    )
    report["period"] = {"from": period_from or None, "to": period_to or None, "skipped": skipped}
    report["customer_links"] = None
    report["already_imported"] = bool(await db.scalar(select(func.count()).select_from(ImportBatch).where(ImportBatch.file_sha256 == sha)))

    if dry_run:
        return report

    batch = ImportBatch(
        id=uuid.uuid4(), filename=(filename or "")[:255] or None, file_sha256=sha,
        uploaded_by=uuid.UUID(user_id) if user_id else None, status="committed",
        years=sorted({y for ys in years.values() for y in ys}),
        counts=report["counts"],
        summary=_jsonable({
            "reconciliation": report["reconciliation"], "issue_counts": report["issue_counts"],
            "changes": report["changes"], "missing": report["missing"], "period": report["period"],
        }),
    )
    db.add(batch)
    await db.flush()

    await _apply(db, batch.id, rw, plans)
    await _save_aliases(db, rw)

    # Attach workbook policies to customers that already exist (by policy, phone or plate). Link-only: no customer
    # is created or changed here. In a savepoint, so if it ever fails the import itself is unaffected.
    try:
        async with db.begin_nested():
            report["customer_links"] = await unified.link_customers(db, create=False, dry_run=False, commit=False)
    except Exception:
        logger.exception("Linking workbook rows to customers failed; the import itself is unaffected")
        report["customer_links"] = None

    # Records posted into the system earlier follow the sheet; new rows are posted only when asked. Savepointed, so a
    # problem here never undoes the import (the ledger is already updated and the rows can be posted from the Post tab).
    report["posting"] = None
    try:
        async with db.begin_nested():
            synced = await posting.resync_posted(db, commit=False)
            posted = await posting.post_ready(db, dry_run=False, commit=False) if post else None
        report["posting"] = {"resynced": synced, "posted": posted}
    except Exception:
        logger.exception("Posting to the system failed; the import itself is unaffected")
        report["posting"] = {"error": "Posting to the system did not complete - the ledger was imported. Run it again from the Post to system tab."}

    report["batch_id"] = str(batch.id)
    record_event(
        "sales_import.commit", entity_type="import_batch", entity_id=batch.id, entity_label=filename,
        summary=(
            f"Imported {filename or 'workbook'}: sales {report['counts']['sales']['new']} new / "
            f"{report['counts']['sales']['updated']} changed / {report['counts']['sales']['missing']} missing"
        ),
        counts=report["counts"],
    )
    await db.commit()
    return report


def _label(kind: str, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": kind, "sheet": row.get("sheet_name"), "row": row.get("sheet_row"),
        "client_name": row.get("client_name") or row.get("details"), "policy_number": row.get("policy_number"),
    }


def _build_report(*, filename, sha, dry_run, pw, rw, recon, plans, existing_by_id) -> dict[str, Any]:
    changes: list[dict[str, Any]] = []
    for kind, plan in plans.items():
        for m in plan.updated:
            changes.append({**_label(kind, m.values), "fields": m.diffs})
    missing: list[dict[str, Any]] = []
    for kind, plan in plans.items():
        for mid in plan.missing_ids:
            row = existing_by_id[kind].get(mid, {})
            missing.append(_label(kind, row))

    severity_order = {"error": 0, "warning": 1}
    issues = sorted(rw.issues, key=lambda i: (severity_order.get(i["severity"], 2), i["sheet"], i["row"]))
    premium = sum((e["premium"] or Decimal(0) for e in rw.sales), Decimal(0))
    commission = sum((e["commission"] or Decimal(0) for e in rw.sales), Decimal(0))

    return _jsonable({
        "dry_run": dry_run,
        "filename": filename,
        "file_sha256": sha,
        "already_imported": False,
        "batch_id": None,
        "sheets": [{"name": s.name, "kind": s.kind, "year": s.year, "rows": s.rows} for s in pw.sheets],
        "ignored_sheets": pw.ignored_sheets,
        "notes": pw.notes,
        "unknown_columns": pw.unknown_columns,
        "counts": {kind: _counts(plan) for kind, plan in plans.items()},
        "totals": {"rows": len(rw.sales), "premium": premium, "commission": commission},
        "reconciliation": recon,
        "issue_counts": rw.issue_counts,
        "issues": issues[:MAX_ISSUES_SHOWN],
        "issues_total": len(issues),
        "changes": changes[:MAX_CHANGES_SHOWN],
        "changes_total": len(changes),
        "missing": missing[:100],
        "missing_total": len(missing),
        "new_aliases": {
            "underwriters": [{"typed": typed, "canonical": canonical} for _, (canonical, typed) in sorted(rw.new_underwriter_aliases.items())],
            "staff": [{"typed": typed, "name": name, "branch": branch} for _, (name, branch, typed) in sorted(rw.new_staff_aliases.items())][:200],
        },
    })


# --------------------------------------------------------------------------------------
# applying a plan
# --------------------------------------------------------------------------------------


async def _apply(db: AsyncSession, batch_id: uuid.UUID, rw, plans: dict[str, SyncPlan]) -> None:
    now = datetime.now(timezone.utc)

    # ---- sales ----------------------------------------------------------------------------
    sales_plan = plans["sales"]
    id_by_key: dict[str, uuid.UUID] = {}
    inserts = []
    for row in sales_plan.inserts:
        new_id = uuid.uuid4()
        id_by_key[row["natural_key"]] = new_id
        inserts.append({**row, "id": new_id, "status": "active", "first_batch_id": batch_id, "last_batch_id": batch_id})
    for chunk in _chunks(inserts):
        await db.execute(insert(SalesEntry), chunk)

    updates = []
    for m in sales_plan.matched:
        id_by_key[m.values["natural_key"]] = m.id
        updates.append({**m.values, "id": m.id, "status": "active", "last_batch_id": batch_id, "updated_at": now})
    for chunk in _chunks(updates):
        await db.execute(update(SalesEntry), chunk)
    await _mark_missing(db, SalesEntry, sales_plan.missing_ids, batch_id, now)

    await _link_policies(db, rw.sales, id_by_key)

    # ---- claims (linked to the sale they belong to) ---------------------------------------
    sales_index = [
        {"id": id_by_key[r["natural_key"]], "reg_no": r["reg_no"], "underwriter": r["underwriter"],
         "start_date": r["start_date"], "expiry_date": r["expiry_date"]}
        for r in rw.sales if r["reg_no"] and r["natural_key"] in id_by_key
    ]
    claims_plan = plans["claims"]
    for row in [*claims_plan.inserts, *[m.values for m in claims_plan.matched]]:
        row["sales_entry_id"] = best_sales_match(row, sales_index)
    await _write_plan(db, LegacyClaim, claims_plan, batch_id, now)

    await _write_plan(db, IpfRemittance, plans["ipf"], batch_id, now)


async def _write_plan(db: AsyncSession, model, plan: SyncPlan, batch_id: uuid.UUID, now: datetime) -> None:
    inserts = [{**r, "id": uuid.uuid4(), "status": "active", "first_batch_id": batch_id, "last_batch_id": batch_id} for r in plan.inserts]
    for chunk in _chunks(inserts):
        await db.execute(insert(model), chunk)
    updates = [{**m.values, "id": m.id, "status": "active", "last_batch_id": batch_id, "updated_at": now} for m in plan.matched]
    for chunk in _chunks(updates):
        await db.execute(update(model), chunk)
    await _mark_missing(db, model, plan.missing_ids, batch_id, now)


async def _mark_missing(db: AsyncSession, model, ids: list, batch_id: uuid.UUID, now: datetime) -> None:
    for chunk in _chunks(ids):
        await db.execute(update(model).where(model.id.in_(chunk)).values(status="missing_from_sheet", last_batch_id=batch_id, updated_at=now))


async def _link_policies(db: AsyncSession, rows: list[dict[str, Any]], id_by_key: dict[str, uuid.UUID]) -> None:
    """A ledger row whose policy number matches a policy in the app points at it."""
    wanted: dict[str, list[str]] = {}
    for r in rows:
        if r.get("policy_number"):
            wanted.setdefault(r["policy_number"], []).append(r["natural_key"])
    if not wanted:
        return
    found: dict[str, uuid.UUID] = {}
    numbers = list(wanted)
    for chunk in _chunks(numbers, 500):
        result = await db.execute(
            select(Policy.id, func.upper(func.replace(Policy.policy_number, " ", "")))
            .where(func.upper(func.replace(Policy.policy_number, " ", "")).in_(chunk))
        )
        found.update({number: pid for pid, number in result.all()})
    links = [{"id": id_by_key[key], "policy_id": pid} for n, pid in found.items() for key in wanted.get(n, []) if key in id_by_key]
    for chunk in _chunks(links):
        await db.execute(update(SalesEntry), chunk)


async def _save_aliases(db: AsyncSession, rw) -> None:
    """Spellings the importer resolved on its own are kept (unconfirmed) so the same decision is
    made every week and an administrator can review it once. Existing aliases are never overwritten."""
    rows = [
        {"id": uuid.uuid4(), "kind": "underwriter", "alias_key": key, "as_typed": typed[:200], "canonical": canonical,
         "branch": None, "confirmed": False, "source": "auto"}
        for key, (canonical, typed) in rw.new_underwriter_aliases.items()
    ] + [
        {"id": uuid.uuid4(), "kind": "staff", "alias_key": key, "as_typed": typed[:200], "canonical": name,
         "branch": branch, "confirmed": False, "source": "auto"}
        for key, (name, branch, typed) in rw.new_staff_aliases.items()
    ]
    for chunk in _chunks(rows):
        await db.execute(pg_insert(ImportAlias).on_conflict_do_nothing(constraint="uq_import_alias_kind_key"), chunk)


# --------------------------------------------------------------------------------------
# reading the ledger
# --------------------------------------------------------------------------------------


async def list_batches(db: AsyncSession, limit: int = 30) -> list[ImportBatch]:
    return list((await db.scalars(select(ImportBatch).order_by(ImportBatch.created_at.desc()).limit(limit))).all())


def _entry_filters(*, year, month, underwriter, staff, branch, q, level, status, product):
    conditions = []
    if year:
        conditions.append(SalesEntry.sheet_year == year)
    if month:
        conditions.append(SalesEntry.period_month == month)
    if underwriter:
        conditions.append(SalesEntry.underwriter == underwriter)
    if staff:
        conditions.append(SalesEntry.staff_name == staff)
    if branch:
        conditions.append(SalesEntry.branch == branch)
    if product:
        conditions.append(SalesEntry.product_line == product)
    if status:
        conditions.append(SalesEntry.status == status)
    if level == "issues":
        conditions.append(SalesEntry.issue_level.in_(("warning", "error")))
    elif level in ("error", "warning"):
        conditions.append(SalesEntry.issue_level == level)
    if q:
        like = f"%{q.strip()}%"
        conditions.append(or_(
            SalesEntry.client_name.ilike(like), SalesEntry.policy_number.ilike(like),
            SalesEntry.reg_no.ilike(like), SalesEntry.phone.ilike(like),
        ))
    return conditions


async def list_entries(db: AsyncSession, *, year=None, month=None, underwriter=None, staff=None, branch=None, q=None,
                       level=None, status=None, product=None, limit=50, offset=0) -> dict[str, Any]:
    where = _entry_filters(year=year, month=month, underwriter=underwriter, staff=staff, branch=branch, q=q, level=level, status=status, product=product)
    totals = (await db.execute(
        select(func.count(), func.coalesce(func.sum(SalesEntry.premium), 0), func.coalesce(func.sum(SalesEntry.commission), 0)).where(*where)
    )).one()
    items = (await db.scalars(
        select(SalesEntry).where(*where)
        .order_by(SalesEntry.period_year.desc(), SalesEntry.period_month.desc().nulls_last(), SalesEntry.date_paid.desc().nulls_last(), SalesEntry.sheet_row)
        .limit(limit).offset(offset)
    )).all()
    return {"total": totals[0], "premium": totals[1], "commission": totals[2], "items": list(items)}


async def entry_options(db: AsyncSession, year: int | None) -> dict[str, list]:
    """Values for the filter drop-downs."""
    async def distinct(column):
        stmt = select(column).where(column.is_not(None))
        if year:
            stmt = stmt.where(SalesEntry.sheet_year == year)
        return [v for (v,) in (await db.execute(stmt.distinct().order_by(column))).all()]

    years = [y for (y,) in (await db.execute(select(SalesEntry.sheet_year).distinct().order_by(SalesEntry.sheet_year.desc()))).all()]
    return {
        "years": years, "underwriters": await distinct(SalesEntry.underwriter),
        "staff": await distinct(SalesEntry.staff_name), "branches": await distinct(SalesEntry.branch),
        "products": await distinct(SalesEntry.product_line),
    }


async def summary(db: AsyncSession, year: int) -> dict[str, Any]:
    base = (SalesEntry.sheet_year == year, SalesEntry.status == "active")

    async def grouped(*columns):
        stmt = (
            select(*columns, func.count(), func.coalesce(func.sum(SalesEntry.premium), 0), func.coalesce(func.sum(SalesEntry.commission), 0))
            .where(*base).group_by(*columns)
        )
        return (await db.execute(stmt)).all()

    monthly = [
        {"year": y, "month": m, "count": n, "premium": p, "commission": c}
        for y, m, n, p, c in sorted(await grouped(SalesEntry.period_year, SalesEntry.period_month), key=lambda r: (r[0], r[1] or 0))
    ]

    def simple(rows, key):
        return sorted(
            [{key: name, "count": n, "premium": p, "commission": c} for name, n, p, c in rows],
            key=lambda r: r["premium"], reverse=True,
        )

    today = date.today()
    window = today + timedelta(days=60)
    expiring_rows = (await db.scalars(
        select(SalesEntry).where(SalesEntry.status == "active", SalesEntry.expiry_date >= today, SalesEntry.expiry_date <= window)
        .order_by(SalesEntry.expiry_date).limit(300)
    )).all()
    expiring = []
    regs = {e.reg_no for e in expiring_rows if e.reg_no}
    later: dict[str, list[tuple[uuid.UUID, date]]] = {}
    if regs:
        for entry_id, reg, start in (await db.execute(
            select(SalesEntry.id, SalesEntry.reg_no, SalesEntry.start_date)
            .where(SalesEntry.reg_no.in_(regs), SalesEntry.status == "active", SalesEntry.start_date.is_not(None))
        )).all():
            later.setdefault(reg, []).append((entry_id, start))
    for e in expiring_rows:
        # Already renewed = another row for the same plate that starts at or after (about) this expiry.
        renewed = bool(e.reg_no) and any(
            other_id != e.id and start >= e.expiry_date - timedelta(days=30) for other_id, start in later.get(e.reg_no, [])
        )
        if not renewed:
            expiring.append({
                "id": str(e.id), "client_name": e.client_name, "phone": e.phone, "underwriter": e.underwriter, "reg_no": e.reg_no,
                "asset_ref": e.asset_ref, "expiry_date": e.expiry_date.isoformat(), "premium": e.premium, "staff_name": e.staff_name, "branch": e.branch,
            })

    return {
        "year": year,
        "monthly": monthly,
        "by_underwriter": simple(await grouped(SalesEntry.underwriter), "underwriter"),
        "by_staff": simple(await grouped(SalesEntry.staff_name), "staff"),
        "by_branch": simple(await grouped(SalesEntry.branch), "branch"),
        "by_business_type": simple(await grouped(SalesEntry.business_type), "business_type"),
        "by_product": simple(await grouped(SalesEntry.product_line), "product"),
        "expiring": expiring,
        "expiring_window_days": 60,
    }


async def list_claims(db: AsyncSession, *, year=None, q=None, outcome=None) -> list[LegacyClaim]:
    stmt = select(LegacyClaim)
    if year:
        stmt = stmt.where(LegacyClaim.period_year == year)
    if outcome:
        stmt = stmt.where(LegacyClaim.outcome == outcome)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(LegacyClaim.client_name.ilike(like), LegacyClaim.reg_or_policy.ilike(like), LegacyClaim.narrative.ilike(like)))
    return list((await db.scalars(stmt.order_by(LegacyClaim.date_reported.desc().nulls_last()).limit(500))).all())


async def list_ipf(db: AsyncSession, *, year=None) -> list[IpfRemittance]:
    stmt = select(IpfRemittance)
    if year:
        stmt = stmt.where(IpfRemittance.period_year == year)
    return list((await db.scalars(stmt.order_by(IpfRemittance.date_paid.desc().nulls_last()).limit(500))).all())


# --------------------------------------------------------------------------------------
# aliases ("Names")
# --------------------------------------------------------------------------------------


async def list_aliases(db: AsyncSession, *, kind: str | None = None, unconfirmed: bool = False) -> list[ImportAlias]:
    stmt = select(ImportAlias)
    if kind:
        stmt = stmt.where(ImportAlias.kind == kind)
    if unconfirmed:
        stmt = stmt.where(ImportAlias.confirmed.is_(False))
    return list((await db.scalars(stmt.order_by(ImportAlias.kind, ImportAlias.canonical, ImportAlias.alias_key))).all())


async def save_alias(db: AsyncSession, alias_id: uuid.UUID, *, canonical: str | None, branch: str | None, confirmed: bool) -> ImportAlias:
    alias = await db.get(ImportAlias, alias_id)
    if alias is None:
        raise LookupError("alias not found")
    alias.canonical = (canonical or "").strip() or None
    alias.branch = (branch or "").strip().upper() or None if alias.kind == "staff" else None
    if alias.kind == "underwriter" and alias.canonical:
        alias.canonical = alias.canonical.upper()
    alias.confirmed = confirmed
    alias.source = "admin"
    await db.commit()
    return alias


async def create_alias(db: AsyncSession, *, kind: str, typed: str, canonical: str | None, branch: str | None) -> ImportAlias:
    key = norm_text(typed)
    if not key:
        raise ValueError("Type the spelling as it appears in the sheet.")
    existing = await db.scalar(select(ImportAlias).where(ImportAlias.kind == kind, ImportAlias.alias_key == key))
    if existing:
        raise ValueError("That spelling already has an entry - edit it instead.")
    alias = ImportAlias(
        id=uuid.uuid4(), kind=kind, alias_key=key, as_typed=typed.strip()[:200],
        canonical=((canonical or "").strip().upper() if kind == "underwriter" else (canonical or "").strip()) or None,
        branch=((branch or "").strip().upper() or None) if kind == "staff" else None, confirmed=True, source="admin",
    )
    db.add(alias)
    await db.commit()
    return alias


async def reapply_aliases(db: AsyncSession) -> dict[str, int]:
    """After names have been edited: re-resolve every ledger row from the text typed in the sheet."""
    uw_aliases, staff_aliases = await _load_aliases(db)
    providers = await _provider_index(db)
    now = datetime.now(timezone.utc)

    entries = (await db.execute(
        select(SalesEntry.id, SalesEntry.underwriter_raw, SalesEntry.staff_raw, SalesEntry.underwriter, SalesEntry.staff_name, SalesEntry.branch)
    )).all()
    resolver = StaffResolver((e.staff_raw for e in entries), staff_aliases)
    updates, staff_changed = [], 0
    for e in entries:
        underwriter = resolve_underwriter(e.underwriter_raw, uw_aliases)[0]
        name, branch, _ = resolver.resolve(e.staff_raw)
        if (underwriter, name, branch) != (e.underwriter, e.staff_name, e.branch):
            staff_changed += (name, branch) != (e.staff_name, e.branch)
            updates.append({"id": e.id, "underwriter": underwriter, "staff_name": name, "branch": branch,
                            "provider_id": _match_provider(underwriter, providers), "updated_at": now})
    for chunk in _chunks(updates):
        await db.execute(update(SalesEntry), chunk)

    other = 0
    for model in (LegacyClaim, IpfRemittance):
        rows = (await db.execute(select(model.id, model.underwriter_raw, model.underwriter))).all()
        changes = []
        for r in rows:
            underwriter = resolve_underwriter(r.underwriter_raw, uw_aliases)[0]
            if underwriter != r.underwriter:
                changes.append({"id": r.id, "underwriter": underwriter, "provider_id": _match_provider(underwriter, providers), "updated_at": now})
        for chunk in _chunks(changes):
            await db.execute(update(model), chunk)
        other += len(changes)

    record_event("sales_import.reapply_aliases", summary=f"Re-applied names to {len(updates)} sales rows", sales_rows=len(updates), other_rows=other)
    await db.commit()
    return {"sales_rows": len(updates), "staff_rows": staff_changed, "other_rows": other}


# --------------------------------------------------------------------------------------
# cleaned export
# --------------------------------------------------------------------------------------

_SALES_EXPORT_FIELDS = [
    "sheet_year", "period_year", "period_month", "sheet_row", "client_name", "phone", "underwriter", "reg_no", "asset_ref",
    "product_line", "start_date", "expiry_date", "date_paid", "staff_name", "branch", "business_type", "policy_number",
    "cover_type", "premium", "commission", "wht", "net_revenue",
]


async def export_workbook(db: AsyncSession, years: list[int] | None) -> bytes:
    sales_stmt = select(SalesEntry).where(SalesEntry.status == "active")
    claims_stmt = select(LegacyClaim).where(LegacyClaim.status == "active")
    ipf_stmt = select(IpfRemittance).where(IpfRemittance.status == "active")
    if years:
        sales_stmt = sales_stmt.where(SalesEntry.sheet_year.in_(years))
        claims_stmt = claims_stmt.where(LegacyClaim.period_year.in_(years))
        ipf_stmt = ipf_stmt.where(IpfRemittance.period_year.in_(years))
    sales = (await db.scalars(sales_stmt)).all()
    claims = (await db.scalars(claims_stmt)).all()
    ipf = (await db.scalars(ipf_stmt)).all()

    sales_rows = [{f: getattr(e, f) for f in _SALES_EXPORT_FIELDS} for e in sales]
    claim_rows = [
        {"period_year": c.period_year, "client_name": c.client_name, "contact": c.contact, "reg_or_policy": c.reg_or_policy,
         "underwriter": c.underwriter, "date_reported": c.date_reported, "narrative": c.narrative, "outcome": c.outcome}
        for c in claims
    ]
    ipf_rows = [
        {"period_year": i.period_year, "underwriter": i.underwriter, "details": i.details, "date_paid": i.date_paid, "amount": i.amount}
        for i in ipf
    ]
    issues = []
    for e in sales:
        for flag in e.flags or []:
            if flag.get("severity") in ("error", "warning"):
                issues.append({
                    "sheet": e.sheet_name, "month": MONTH_NAMES[e.period_month - 1] if e.period_month else None,
                    "client_name": e.client_name, "policy_number": e.policy_number,
                    "severity": flag["severity"], "message": flag.get("message"),
                })
    issues.sort(key=lambda i: (i["severity"] != "error", i["sheet"] or "", i["client_name"] or ""))
    record_event("sales_import.export", summary="Downloaded the cleaned sales workbook", years=years or "all", sales_rows=len(sales_rows))
    return await asyncio.to_thread(build_cleaned_workbook, sales_rows, claim_rows, ipf_rows, issues, years)


# --------------------------------------------------------------------------------------
# suggested fixes (a person accepts each one)
# --------------------------------------------------------------------------------------


async def list_suggestions(db: AsyncSession, year: int | None = None) -> list[dict[str, Any]]:
    """Rows where the importer found a likely date fix. Nothing has been changed on these rows."""
    stmt = select(SalesEntry).where(SalesEntry.status == "active", SalesEntry.issue_level.in_(("warning", "error")))
    if year:
        stmt = stmt.where(SalesEntry.sheet_year == year)
    out = []
    for e in (await db.scalars(stmt.order_by(SalesEntry.sheet_year.desc(), SalesEntry.sheet_row))).all():
        for flag in e.flags or []:
            fix = flag.get("fix")
            if not fix:
                continue
            current = getattr(e, fix["field"])
            if current is not None and current.isoformat() == fix["value"]:
                continue
            out.append({
                "entry_id": str(e.id), "client_name": e.client_name, "policy_number": e.policy_number, "underwriter": e.underwriter,
                "sheet": e.sheet_name, "row": e.sheet_row, "field": fix["field"], "label": fix["label"],
                "current": current.isoformat() if current else None, "suggested": fix["value"], "reason": flag.get("message"),
                "start_date": e.start_date.isoformat() if e.start_date else None,
                "expiry_date": e.expiry_date.isoformat() if e.expiry_date else None,
                "date_paid": e.date_paid.isoformat() if e.date_paid else None,
            })
    return out


async def apply_suggestions(db: AsyncSession, items: list[tuple[uuid.UUID, str, date]]) -> dict[str, Any]:
    """Applies the fixes a person ticked. Each must be exactly what the importer suggested for that
    row (a value typed in by hand is refused), and is remembered as an override so the next upload
    of the still-uncorrected sheet does not undo it. Per-row changes are captured in the audit trail."""
    applied, skipped = [], []
    for entry_id, field_name, value in items:
        entry = await db.get(SalesEntry, entry_id)
        if entry is None:
            skipped.append({"entry_id": str(entry_id), "reason": "That row no longer exists."})
            continue
        flag = next((f for f in entry.flags or [] if f.get("fix") and f["fix"]["field"] == field_name and f["fix"]["value"] == value.isoformat()), None)
        if flag is None:
            skipped.append({"entry_id": str(entry_id), "reason": "That suggestion is out of date - the sheet row has changed since."})
            continue
        current = getattr(entry, field_name)
        overrides = dict(entry.overrides or {})
        sheet_value = overrides.get(field_name, {}).get("sheet") or (current.isoformat() if current else None)
        overrides[field_name] = {"value": value.isoformat(), "sheet": sheet_value}
        label = flag["fix"]["label"]
        flags = [f for f in entry.flags or [] if f.get("code") not in FIX_RESOLVES]
        flags.append({
            "code": "fix_applied", "severity": "info",
            "message": f"The {label} in the sheet ({current:%d/%m/%Y}) was changed to {value:%d/%m/%Y} when a suggested fix was accepted. "
                       "Correct it in the sheet and this note goes away." if current else f"The {label} was set to {value:%d/%m/%Y}.",
        })
        setattr(entry, field_name, value)
        entry.overrides = overrides
        entry.flags = flags
        entry.issue_level = level_of(flags)
        applied.append({"entry_id": str(entry_id), "client_name": entry.client_name, "field": field_name,
                        "old": current.isoformat() if current else None, "new": value.isoformat()})
    record_event("sales_import.apply_fixes", summary=f"Accepted {len(applied)} suggested date fix(es)", fixes=applied[:50])
    await db.commit()
    return {"applied": len(applied), "skipped": skipped}
