from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_roles
from app.schemas.application import PolicyOut
from app.services.policy_service import issue_policy

router = APIRouter(prefix="/api/v1/policies", tags=["policies"])


@router.post("/issue/{application_id}", response_model=PolicyOut)
async def issue(
    application_id: str,
    db: AsyncSession = Depends(get_db),
    _claims: dict = Depends(require_roles("super_admin", "operations", "underwriter")),
):
    """Issuance is staff-triggered in Phase 2 - human-in-the-loop per spec
    §47, until Phase 6's automation engine wires this to payment
    confirmation automatically."""
    return await issue_policy(db, application_id)
