"""Admin endpoints for posting workbook rows into the system's own tables (customers, quotes, policies, payments),
linking the workbook's underwriters to providers, and undoing a posting."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_roles
from app.services.sales_import import posting

router = APIRouter(prefix="/api/v1/admin/sales-import/posting", tags=["sales-import-posting"])

READ = Depends(require_roles("super_admin", "management", "finance_officer"))
MANAGE = Depends(require_roles("super_admin", "management"))
DANGER = Depends(require_roles("super_admin"))


class LinkIn(BaseModel):
    underwriter: str
    provider_id: uuid.UUID | None = None
    create_new: bool = False


@router.get("/status", dependencies=[READ])
async def status(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    return await posting.status(db)


@router.get("/overview", dependencies=[READ])
async def overview(
    reason: str | None = None, code: str | None = None, limit: int = Query(50, ge=1, le=200), db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """The whole Post to system tab in one response (status, waiting rows, posted-to-review rows, underwriters)."""
    return await posting.overview(db, reason=reason, code=code, limit=limit)


@router.get("/held", dependencies=[READ])
async def held(reason: str | None = None, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    return await posting.held_entries(db, reason=reason, limit=limit, offset=offset)


@router.get("/review", dependencies=[READ])
async def review(code: str | None = None, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Posted records that carry a flag to review (no phone, placeholder policy number, assumed date...)."""
    return await posting.posted_with_flags(db, code=code, limit=limit, offset=offset)


@router.post("/run", dependencies=[MANAGE])
async def run(dry_run: bool = Query(True, description="True = only report what would be posted"), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    result = await posting.post_ready(db, dry_run=dry_run)
    if not dry_run:
        result["resynced"] = await posting.resync_posted(db)
    return result


@router.get("/underwriters", dependencies=[READ])
async def underwriters(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    return await posting.underwriter_overview(db)


@router.post("/underwriters/auto", dependencies=[MANAGE])
async def auto_link(db: AsyncSession = Depends(get_db)) -> dict[str, int]:
    return {"linked": await posting.auto_link_underwriters(db)}


@router.put("/underwriters", dependencies=[MANAGE])
async def link(payload: LinkIn, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    if not payload.create_new and payload.provider_id is None:
        raise HTTPException(status_code=400, detail="Choose a provider, or ask for a new one to be created.")
    try:
        return await posting.link_underwriter(db, payload.underwriter, provider_id=payload.provider_id, create_new=payload.create_new)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/unpost", dependencies=[DANGER])
async def unpost(dry_run: bool = Query(True), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    return await posting.unpost(db, dry_run=dry_run)
