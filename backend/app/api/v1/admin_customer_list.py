"""Admin Customers list (and CSV download). The existing customer page (/admin/customers/{id}) is unchanged; this only adds
the list that leads to it."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.context import record_event
from app.core.database import get_db
from app.core.security import require_roles
from app.services import customer_list_service as service

# A separate prefix from /api/v1/admin/customers so "export" can never be mistaken for a customer id.
router = APIRouter(prefix="/api/v1/admin/customer-list", tags=["admin-customers"])

READ = Depends(require_roles("super_admin", "operations", "management", "sales_agent", "customer_support", "claims_officer"))
EXPORT = Depends(require_roles("super_admin", "operations", "management"))


class CustomerRow(BaseModel):
    id: str
    full_name: str
    phone: str | None = None
    email: str | None = None
    lead_source: str | None = None
    created_at: datetime | None = None
    policies: int
    active_policies: int
    premium: Decimal
    next_expiry: date | None = None
    has_workbook: bool


class CustomerPage(BaseModel):
    total: int
    items: list[CustomerRow]
    stats: dict[str, int]
    sources: list[str]


def _filters(q, lead_source, has_phone, policy, sort):
    return dict(q=q, lead_source=lead_source, has_phone=has_phone, policy=policy, sort=sort)


@router.get("", response_model=CustomerPage, dependencies=[READ])
async def customers(
    q: str | None = None,
    lead_source: str | None = None,
    has_phone: bool | None = None,
    policy: str | None = Query(None, pattern="^(active|expiring|expired|none)$"),
    sort: str = Query("newest", pattern="^(newest|name|expiry|premium)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> Any:
    page = await service.list_customers(db, limit=limit, offset=offset, **_filters(q, lead_source, has_phone, policy, sort))
    for item in page["items"]:
        item["id"] = str(item["id"])
    return page


@router.get("/export", dependencies=[EXPORT])
async def export(
    q: str | None = None,
    lead_source: str | None = None,
    has_phone: bool | None = None,
    policy: str | None = Query(None, pattern="^(active|expiring|expired|none)$"),
    sort: str = Query("newest", pattern="^(newest|name|expiry|premium)$"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    content = await service.export_csv(db, **_filters(q, lead_source, has_phone, policy, sort))
    record_event("customers.export", summary="Downloaded the customers list as CSV", rows=content.count("\n") - 1)
    return Response(content=content, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="customers.csv"'})
