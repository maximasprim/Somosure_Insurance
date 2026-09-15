from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_claims, require_roles
from app.models.sticker import Sticker
from app.schemas.automation import StickerAdvanceRequest, StickerOut
from app.services.sticker_service import advance_sticker

router = APIRouter(
    prefix="/api/v1/admin/stickers",
    tags=["stickers"],
    dependencies=[Depends(require_roles("super_admin", "operations"))],
)


@router.get("", response_model=list[StickerOut])
async def list_stickers(db: AsyncSession = Depends(get_db), status_filter: str | None = None):
    stmt = select(Sticker).order_by(Sticker.created_at.desc())
    if status_filter:
        stmt = stmt.where(Sticker.status == status_filter)
    return (await db.scalars(stmt)).all()


@router.post("/{sticker_id}/advance", response_model=StickerOut)
async def advance(
    sticker_id: str,
    payload: StickerAdvanceRequest,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(get_current_claims),
):
    return await advance_sticker(db, sticker_id, payload.to_status, claims.get("sub"), payload.notes)
