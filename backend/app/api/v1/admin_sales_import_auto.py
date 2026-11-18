"""Admin endpoints for the automatic Google Sheet import and the import version history (Sales import ->
Automation and Versions tabs). Same roles as the rest of Sales import; changing settings and reverting need
super_admin or management."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_claims, require_roles
from app.schemas.sales_automation import AutomationSettingsIn, RevertIn
from app.services.sales_import import auto_import, versions
from app.services.sales_import.parser import WorkbookError

router = APIRouter(prefix="/api/v1/admin/sales-import", tags=["sales-import-automation"])

READ = Depends(require_roles("super_admin", "management", "finance_officer"))
MANAGE = Depends(require_roles("super_admin", "management"))

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# --- automatic import ------------------------------------------------------------------------


@router.get("/automation", dependencies=[READ])
async def get_automation(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    row = await auto_import.get_settings_row(db)
    await db.commit()
    return {"settings": auto_import.settings_view(row), "runs": await auto_import.list_runs(db)}


@router.put("/automation", dependencies=[MANAGE])
async def save_automation(payload: AutomationSettingsIn, db: AsyncSession = Depends(get_db), claims: dict = Depends(get_current_claims)) -> dict[str, Any]:
    try:
        row = await auto_import.update_settings(db, payload.model_dump(), user_id=claims.get("sub"))
    except auto_import.SettingsError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return auto_import.settings_view(row)


@router.post("/automation/run-now", dependencies=[MANAGE])
async def run_now(db: AsyncSession = Depends(get_db), claims: dict = Depends(get_current_claims)) -> dict[str, Any]:
    """Pulls the sheet and imports what changed, right now (does not move the schedule)."""
    try:
        return await auto_import.run_sync(db, trigger="run_now", user_id=claims.get("sub"))
    except auto_import.SettingsError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/automation/resume", dependencies=[MANAGE])
async def resume_automation(db: AsyncSession = Depends(get_db), claims: dict = Depends(get_current_claims)) -> dict[str, Any]:
    return auto_import.settings_view(await auto_import.resume(db, user_id=claims.get("sub")))


# --- versions --------------------------------------------------------------------------------


@router.get("/versions", dependencies=[READ])
async def list_versions(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    return await versions.list_versions(db, limit=limit, offset=offset)


@router.get("/versions/{version_id}/download", dependencies=[READ])
async def download_version(version_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    try:
        version = await versions.get(db, version_id)
        content = await versions.read_file(version)
    except LookupError:
        raise HTTPException(status_code=404, detail="Version not found")
    except versions.VersionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return Response(content=content, media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="sales-report-v{version.version_no}.xlsx"'})


@router.get("/versions/{version_id}/revert-preview", dependencies=[MANAGE])
async def revert_preview(version_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """What going back to this version would change. Nothing is saved."""
    try:
        return await auto_import.revert_preview(db, version_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Version not found")
    except (versions.VersionError, WorkbookError) as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/versions/{version_id}/revert", dependencies=[MANAGE])
async def revert(version_id: uuid.UUID, payload: RevertIn, db: AsyncSession = Depends(get_db), claims: dict = Depends(get_current_claims)) -> dict[str, Any]:
    try:
        return await auto_import.revert(db, version_id, user_id=claims.get("sub"), reason=payload.reason)
    except LookupError:
        raise HTTPException(status_code=404, detail="Version not found")
    except (versions.VersionError, WorkbookError) as exc:
        raise HTTPException(status_code=409, detail=str(exc))
