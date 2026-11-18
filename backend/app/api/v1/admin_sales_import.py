"""Admin endpoints for the weekly sales report: upload (preview, then import), the ledger it builds,
summaries, the names screen, and the cleaned workbook download."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_claims, require_roles
from app.schemas.sales_import import (
    AliasCreate,
    ApplyFixes,
    AliasOut,
    AliasUpdate,
    EntryOptions,
    ImportBatchOut,
    IpfRemittanceOut,
    LegacyClaimOut,
    SalesEntryPage,
)
from app.services.sales_import import service, versions
from app.services.sales_import.parser import WorkbookError

ROLES = ("super_admin", "management", "finance_officer")

router = APIRouter(
    prefix="/api/v1/admin/sales-import",
    tags=["sales-import"],
    dependencies=[Depends(require_roles(*ROLES))],
)

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.post("/upload")
async def upload_workbook(
    file: UploadFile = File(...),
    dry_run: bool = Query(True, description="True = check the file and report what would change; False = import it"),
    post: bool = Query(False, description="After importing, also post new rows into the system (customers, quotes, policies, payments)"),
    from_period: str | None = Query(None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="Only import from this month on, e.g. 2025-01"),
    to_period: str | None = Query(None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="Only import up to this month, e.g. 2026-11"),
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(get_current_claims),
) -> dict[str, Any]:
    name = (file.filename or "").lower()
    if not name.endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="Upload the Excel workbook as an .xlsx file.")
    data = await file.read()
    try:
        return await service.run_import(
            db, filename=file.filename, data=data, dry_run=dry_run, user_id=claims.get("sub"), period_from=from_period, period_to=to_period, post=post,
        )
    except WorkbookError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except versions.VersionError as exc:
        await db.rollback()
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/batches", response_model=list[ImportBatchOut])
async def batches(db: AsyncSession = Depends(get_db)):
    return await service.list_batches(db)


@router.get("/entries", response_model=SalesEntryPage)
async def entries(
    year: int | None = None,
    month: int | None = Query(None, ge=1, le=12),
    underwriter: str | None = None,
    staff: str | None = None,
    branch: str | None = None,
    product: str | None = None,
    q: str | None = None,
    level: str | None = Query(None, pattern="^(issues|error|warning)$"),
    status: str | None = Query(None, pattern="^(active|missing_from_sheet)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_entries(
        db, year=year, month=month, underwriter=underwriter, staff=staff, branch=branch, product=product,
        q=q, level=level, status=status, limit=limit, offset=offset,
    )


@router.get("/entries/options", response_model=EntryOptions)
async def entry_options(year: int | None = None, db: AsyncSession = Depends(get_db)):
    return await service.entry_options(db, year)


@router.get("/summary")
async def summary(year: int, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    return _plain(await service.summary(db, year))


@router.get("/claims", response_model=list[LegacyClaimOut])
async def claims_ledger(year: int | None = None, q: str | None = None, outcome: str | None = None, db: AsyncSession = Depends(get_db)):
    return await service.list_claims(db, year=year, q=q, outcome=outcome)


@router.get("/ipf", response_model=list[IpfRemittanceOut])
async def ipf_ledger(year: int | None = None, db: AsyncSession = Depends(get_db)):
    return await service.list_ipf(db, year=year)


# --- suggested fixes -------------------------------------------------------------------------


@router.get("/suggestions")
async def suggestions(year: int | None = None, db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    return await service.list_suggestions(db, year)


@router.post("/suggestions/apply")
async def apply_suggestions(payload: ApplyFixes, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    return await service.apply_suggestions(db, [(i.entry_id, i.field, i.value) for i in payload.items])


# --- names -----------------------------------------------------------------------------------


@router.get("/aliases", response_model=list[AliasOut])
async def aliases(kind: str | None = Query(None, pattern="^(underwriter|staff)$"), unconfirmed: bool = False, db: AsyncSession = Depends(get_db)):
    return await service.list_aliases(db, kind=kind, unconfirmed=unconfirmed)


@router.post("/aliases", response_model=AliasOut, status_code=201)
async def add_alias(payload: AliasCreate, db: AsyncSession = Depends(get_db)):
    try:
        return await service.create_alias(db, kind=payload.kind, typed=payload.typed, canonical=payload.canonical, branch=payload.branch)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/aliases/reapply")
async def reapply_aliases(db: AsyncSession = Depends(get_db)) -> dict[str, int]:
    return await service.reapply_aliases(db)


@router.put("/aliases/{alias_id}", response_model=AliasOut)
async def update_alias(alias_id: uuid.UUID, payload: AliasUpdate, db: AsyncSession = Depends(get_db)):
    try:
        return await service.save_alias(db, alias_id, canonical=payload.canonical, branch=payload.branch, confirmed=payload.confirmed)
    except LookupError:
        raise HTTPException(status_code=404, detail="Name not found")


# --- cleaned workbook ------------------------------------------------------------------------


@router.get("/export")
async def export_cleaned(years: str | None = Query(None, description="Comma-separated years, e.g. 2026,2025; empty = all"), db: AsyncSession = Depends(get_db)):
    try:
        wanted = [int(y) for y in years.split(",") if y.strip()] if years else None
    except ValueError:
        raise HTTPException(status_code=400, detail="years must be numbers like 2026,2025")
    content = await service.export_workbook(db, wanted)
    label = "-".join(str(y) for y in wanted) if wanted else "all"
    return Response(content=content, media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="sales-report-cleaned-{label}.xlsx"'})


def _plain(value: Any) -> Any:
    """Decimals/dates -> JSON-friendly values for the hand-built summary payload."""
    from datetime import date as _date
    from decimal import Decimal

    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, _date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value
