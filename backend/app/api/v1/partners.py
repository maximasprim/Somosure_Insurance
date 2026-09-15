import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_roles
from app.models.partner import Partner

router = APIRouter(
    prefix="/api/v1/admin/partners",
    tags=["partners"],
    dependencies=[Depends(require_roles("super_admin", "management"))],
)


class PartnerCreate(BaseModel):
    name: str
    partner_type: str
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None


class PartnerOut(BaseModel):
    id: uuid.UUID
    name: str
    partner_type: str
    contact_name: str | None
    contact_email: str | None
    contact_phone: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("", response_model=list[PartnerOut])
async def list_partners(db: AsyncSession = Depends(get_db)):
    return (await db.scalars(select(Partner))).all()


@router.post("", response_model=PartnerOut)
async def create_partner(payload: PartnerCreate, db: AsyncSession = Depends(get_db)):
    partner = Partner(id=uuid.uuid4(), **payload.model_dump())
    db.add(partner)
    await db.commit()
    await db.refresh(partner)
    return partner
