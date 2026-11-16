"""Admin endpoints that show platform and workbook data together: all sales, one renewals worklist,
linking workbook clients to customers, and a customer's workbook history.

Read-only except for: renewal follow-up notes on workbook policies, adding a phone number for a
workbook client, and linking/creating customers (which is explicit and has a dry run). Nothing here
touches policies, applications, quotes or payments, and nothing sends a message."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_claims, require_roles
from app.schemas.sales_import import (
    ClientPhoneIn,
    CustomerHistoryOut,
    FollowUpIn,
    ManualSaleIn,
    RenewalPage,
    UnifiedSalesPage,
    EntryOptions,
)
from app.services.sales_import import manual, unified

router = APIRouter(prefix="/api/v1/admin/sales", tags=["admin-sales"])

READ = Depends(require_roles("super_admin", "management", "finance_officer", "operations", "sales_agent"))
MANAGE = Depends(require_roles("super_admin", "management", "operations"))
RECORD = Depends(require_roles("super_admin", "management", "operations", "sales_agent", "finance_officer"))
HISTORY = Depends(require_roles("super_admin", "operations", "management", "sales_agent", "customer_support", "claims_officer"))


@router.get("", response_model=UnifiedSalesPage, dependencies=[READ])
async def all_sales(
    source: str | None = Query(None, pattern="^(platform|workbook|manual)$"),
    year: int | None = None,
    month: int | None = Query(None, ge=1, le=12),
    underwriter: str | None = None,
    staff: str | None = None,
    branch: str | None = None,
    product: str | None = None,
    business_type: str | None = Query(None, pattern="^(new_business|renewal)$"),
    q: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await unified.sales_page(
        db, limit=limit, offset=offset, source=source, year=year, month=month, underwriter=underwriter,
        staff=staff, branch=branch, product=product, business_type=business_type, q=q,
    )


@router.get("/options", response_model=EntryOptions, dependencies=[READ])
async def sales_options(db: AsyncSession = Depends(get_db)):
    return await unified.sales_options(db)


# --- renewals ---------------------------------------------------------------------------------


@router.get("/renewals", response_model=RenewalPage, dependencies=[READ])
async def renewals(
    days: int = Query(60, ge=1, le=365),
    overdue_days: int = Query(30, ge=0, le=365),
    source: str | None = Query(None, pattern="^(platform|workbook)$"),
    status: str | None = Query(None, pattern="^(due|contacted|quoted|paid|renewed|lost)$"),
    q: str | None = None,
    include_closed: bool = False,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await unified.renewals_page(
        db, days=days, overdue_days=overdue_days, source=source, status=status, q=q,
        include_closed=include_closed, limit=limit, offset=offset,
    )


@router.put("/renewals/{entry_id}", dependencies=[READ])
async def follow_up(entry_id: uuid.UUID, payload: FollowUpIn, db: AsyncSession = Depends(get_db), claims: dict = Depends(get_current_claims)) -> dict[str, Any]:
    try:
        entry = await unified.set_follow_up(db, entry_id, status=payload.status, note=payload.note, user_id=claims.get("sub"))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"id": str(entry.id), "status": entry.follow_up_status or "due", "note": entry.follow_up_note}


# --- customers --------------------------------------------------------------------------------


@router.get("/customers/status", dependencies=[READ])
async def customer_status(db: AsyncSession = Depends(get_db)) -> dict[str, int]:
    return await unified.customer_link_status(db)


@router.post("/customers/link", dependencies=[MANAGE])
async def link_customers(
    create: bool = Query(False, description="Also create customers for workbook clients that have a phone number and match nobody"),
    dry_run: bool = Query(True, description="True = only report what would happen"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    return await unified.link_customers(db, create=create, dry_run=dry_run)


@router.get("/customers/needs-phone", dependencies=[READ])
async def needs_phone(q: str | None = None, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    return await unified.clients_needing_phone(db, q=q, limit=limit, offset=offset)


@router.post("/customers/phone", dependencies=[MANAGE])
async def add_phone(payload: ClientPhoneIn, db: AsyncSession = Depends(get_db), claims: dict = Depends(get_current_claims)) -> dict[str, int]:
    try:
        return await unified.set_client_phone(db, client_key=payload.client_key, phone_text=payload.phone, user_id=claims.get("sub"))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/customers/{customer_id}/history", response_model=CustomerHistoryOut, dependencies=[HISTORY])
async def customer_history(customer_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await unified.customer_history(db, customer_id)


# --- recording a sale directly in the system ---------------------------------------------------


@router.get("/record/options", dependencies=[RECORD])
async def record_options(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    return await manual.options(db)


@router.post("/record", dependencies=[RECORD])
async def record_sale(payload: ManualSaleIn, db: AsyncSession = Depends(get_db), claims: dict = Depends(get_current_claims)) -> dict[str, Any]:
    try:
        return await manual.record_sale(db, payload.model_dump(), claims.get("sub"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/record/recent", dependencies=[RECORD])
async def recent_sales(limit: int = Query(15, ge=1, le=50), db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    return await manual.recent(db, limit)


@router.delete("/record/{entry_id}", dependencies=[MANAGE])
async def void_sale(entry_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    try:
        return await manual.void_sale(db, entry_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
