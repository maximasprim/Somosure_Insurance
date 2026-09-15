from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_claims, require_roles
from app.models.crm import Lead, LeadActivity
from app.models.customer import Customer
from app.schemas.crm import (
    FunnelOut,
    LeadActivityCreate,
    LeadActivityOut,
    LeadUpdate,
    LeadWithCustomerOut,
)
from app.services.lead_service import add_activity, get_funnel, update_lead

router = APIRouter(
    prefix="/api/v1/admin/leads",
    tags=["crm"],
    dependencies=[Depends(require_roles("super_admin", "management", "sales_agent", "marketing"))],
)


@router.get("", response_model=list[LeadWithCustomerOut])
async def list_leads(
    db: AsyncSession = Depends(get_db),
    stage: str | None = None,
    source: str | None = None,
    agent_id: str | None = None,
):
    stmt = select(Lead, Customer).join(Customer, Lead.customer_id == Customer.id).order_by(Lead.updated_at.desc())
    if stage:
        stmt = stmt.where(Lead.stage == stage)
    if source:
        stmt = stmt.where(Lead.source == source)
    if agent_id:
        stmt = stmt.where(Lead.assigned_agent_id == agent_id)

    rows = (await db.execute(stmt)).all()
    return [
        LeadWithCustomerOut(
            id=str(lead.id),
            customer_id=str(lead.customer_id),
            stage=lead.stage,
            source=lead.source,
            product_interest=lead.product_interest,
            assigned_agent_id=str(lead.assigned_agent_id) if lead.assigned_agent_id else None,
            quote_request_id=str(lead.quote_request_id) if lead.quote_request_id else None,
            created_at=lead.created_at,
            updated_at=lead.updated_at,
            customer_name=customer.full_name,
            customer_phone=customer.phone,
        )
        for lead, customer in rows
    ]


@router.get("/funnel", response_model=FunnelOut)
async def funnel(db: AsyncSession = Depends(get_db)):
    return await get_funnel(db)


@router.patch("/{lead_id}")
async def patch_lead(lead_id: str, payload: LeadUpdate, db: AsyncSession = Depends(get_db)):
    lead = await update_lead(db, lead_id, payload.stage, payload.assigned_agent_id)
    return {
        "id": str(lead.id),
        "stage": lead.stage,
        "assigned_agent_id": str(lead.assigned_agent_id) if lead.assigned_agent_id else None,
    }


@router.post("/{lead_id}/activities", response_model=LeadActivityOut)
async def create_activity(
    lead_id: str,
    payload: LeadActivityCreate,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(get_current_claims),
):
    return await add_activity(db, lead_id, payload.activity_type, payload.notes, claims.get("sub"))


@router.get("/{lead_id}/activities", response_model=list[LeadActivityOut])
async def list_activities(lead_id: str, db: AsyncSession = Depends(get_db)):
    return (
        await db.scalars(
            select(LeadActivity).where(LeadActivity.lead_id == lead_id).order_by(LeadActivity.created_at.desc())
        )
    ).all()
