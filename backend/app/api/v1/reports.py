import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_roles
from app.services.analytics_buckets import ALLOWED_RANGES
from app.services.analytics_service import get_analytics
from app.services.report_service import get_overview, get_provider_performance

router = APIRouter(
    prefix="/api/v1/admin/reports",
    tags=["reports"],
    dependencies=[Depends(require_roles("super_admin", "management", "finance_officer"))],
)


@router.get("/overview")
async def overview(db: AsyncSession = Depends(get_db)):
    return await get_overview(db)


@router.get("/analytics")
async def analytics(days: int = Query(30), db: AsyncSession = Depends(get_db)):
    """Everything the admin dashboard charts, for the last `days` days (7, 30, 90
    or 365) compared with the period before. Same roles as the other reports."""
    if days not in ALLOWED_RANGES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, f"days must be one of {', '.join(str(d) for d in ALLOWED_RANGES)}"
        )
    return await get_analytics(db, days)


@router.get("/provider-performance")
async def provider_performance(db: AsyncSession = Depends(get_db)):
    return await get_provider_performance(db)


@router.get("/provider-performance/export.csv")
async def export_provider_performance(db: AsyncSession = Depends(get_db)):
    rows = await get_provider_performance(db)

    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer, fieldnames=["provider_id", "name", "provider_type", "status", "quotes_returned", "policies_issued"]
    )
    writer.writeheader()
    writer.writerows(rows)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=provider_performance.csv"},
    )
