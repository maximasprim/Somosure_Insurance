"""Public 'Become a partner' form endpoint - no login needed."""

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.rate_limit import limiter
from app.schemas.partner_application import PartnerApplicationIn, PartnerApplicationReceipt
from app.services.partner_application_service import alert_team, snapshot, submit_application

router = APIRouter(prefix="/api/v1/partner-applications", tags=["partner-applications"])


@router.post("", response_model=PartnerApplicationReceipt, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def apply_to_partner(
    request: Request, payload: PartnerApplicationIn, background: BackgroundTasks, db: AsyncSession = Depends(get_db)
):
    """Records the application and alerts the team (after the applicant has been
    answered, so a slow mail server never makes the form hang)."""
    if payload.fax:
        # Honeypot filled in: this is a bot. Look successful, store nothing.
        return PartnerApplicationReceipt(reference="SOM-PTR-0000-000000")
    application, is_new = await submit_application(db, payload)
    if is_new:
        background.add_task(alert_team, snapshot(application))
    return PartnerApplicationReceipt(reference=application.reference)
