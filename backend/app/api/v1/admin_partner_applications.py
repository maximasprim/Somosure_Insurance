"""Staff queue for partner applications: review, then approve or decline - both
with a reason. Approving creates the partner (see partner_application_service)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_claims, require_roles
from app.models.partner import PartnerApplication
from app.schemas.partner_application import (
    ApproveIn,
    ApproveOut,
    DeclineIn,
    PartnerApplicationOut,
    PartnerApplicationPage,
)
from app.services import partner_application_service as svc

router = APIRouter(
    prefix="/api/v1/admin/partner-applications",
    tags=["admin-partner-applications"],
    dependencies=[Depends(require_roles("super_admin", "management"))],
)


@router.get("", response_model=PartnerApplicationPage)
async def list_applications(
    status_: str | None = Query(None, alias="status", pattern="^(pending|approved|declined)$"),
    q: str | None = None,
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    conds = []
    if status_:
        conds.append(PartnerApplication.status == status_)
    if q:
        like = f"%{q.strip()}%"
        conds.append(
            or_(
                PartnerApplication.business_name.ilike(like),
                PartnerApplication.contact_name.ilike(like),
                PartnerApplication.contact_email.ilike(like),
                PartnerApplication.contact_phone.ilike(like),
                PartnerApplication.reference.ilike(like),
            )
        )
    total = await db.scalar(select(func.count()).select_from(PartnerApplication).where(*conds)) or 0
    pending = await db.scalar(select(func.count()).select_from(PartnerApplication).where(PartnerApplication.status == "pending")) or 0
    rows = (
        await db.scalars(
            # Waiting applications first, longest-waiting at the top; decided ones after, newest first.
            select(PartnerApplication)
            .where(*conds)
            .order_by(
                (PartnerApplication.status != "pending"),
                case((PartnerApplication.status == "pending", PartnerApplication.created_at), else_=None).asc(),
                PartnerApplication.created_at.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return PartnerApplicationPage(
        items=[PartnerApplicationOut.model_validate(r) for r in rows], total=total, limit=limit, offset=offset, pending_count=pending
    )


@router.get("/{application_id}", response_model=PartnerApplicationOut)
async def get_application(application_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    application = await db.get(PartnerApplication, application_id)
    if not application:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    return application


@router.post("/{application_id}/approve", response_model=ApproveOut)
async def approve(
    application_id: uuid.UUID, payload: ApproveIn, db: AsyncSession = Depends(get_db), claims: dict = Depends(get_current_claims)
):
    """Creates the partner record and, if asked, enrols the contact as an
    affiliate with an optional special commission rate and/or discount credit."""
    return await svc.approve_application(db, application_id, str(claims.get("sub")), payload)


@router.post("/{application_id}/decline", response_model=PartnerApplicationOut)
async def decline(
    application_id: uuid.UUID, payload: DeclineIn, db: AsyncSession = Depends(get_db), claims: dict = Depends(get_current_claims)
):
    return await svc.decline_application(db, application_id, str(claims.get("sub")), payload.reason)
