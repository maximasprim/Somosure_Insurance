import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_roles
from app.services.report_service import get_overview, get_provider_performance

router = APIRouter(
    prefix="/api/v1/admin/reports",
    tags=["reports"],
    dependencies=[Depends(require_roles("super_admin", "management", "finance_officer"))],
)


@router.get("/overview")
async def overview(db: AsyncSession = Depends(get_db)):
    return await get_overview(db)


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
