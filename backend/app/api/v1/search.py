from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_roles
from app.services.search_service import global_search

router = APIRouter(
    prefix="/api/v1/admin/search",
    tags=["search"],
    dependencies=[Depends(require_roles("super_admin", "operations", "management", "sales_agent", "customer_support", "claims_officer"))],
)


@router.get("")
async def search(q: str = Query(..., min_length=2), db: AsyncSession = Depends(get_db)):
    return await global_search(db, q)
