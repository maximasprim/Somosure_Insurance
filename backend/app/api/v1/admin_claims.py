from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_claims, require_roles
from app.models.claim import Claim, ClaimEvent
from app.schemas.claim import ClaimEventOut, ClaimOut, ClaimTransitionRequest
from app.services.claim_service import transition_claim

router = APIRouter(
    prefix="/api/v1/admin/claims",
    tags=["claims"],
    dependencies=[Depends(require_roles("super_admin", "operations", "claims_officer", "management"))],
)


@router.get("", response_model=list[ClaimOut])
async def list_claims(db: AsyncSession = Depends(get_db), status_filter: str | None = None):
    stmt = select(Claim).order_by(Claim.created_at.desc())
    if status_filter:
        stmt = stmt.where(Claim.status == status_filter)
    return (await db.scalars(stmt)).all()


@router.post("/{claim_id}/transition", response_model=ClaimOut)
async def transition(
    claim_id: str,
    payload: ClaimTransitionRequest,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(get_current_claims),
):
    return await transition_claim(db, claim_id, payload.to_status, claims.get("sub"), payload.notes)


@router.get("/{claim_id}/events", response_model=list[ClaimEventOut])
async def list_events(claim_id: str, db: AsyncSession = Depends(get_db)):
    return (
        await db.scalars(select(ClaimEvent).where(ClaimEvent.claim_id == claim_id).order_by(ClaimEvent.created_at.desc()))
    ).all()
