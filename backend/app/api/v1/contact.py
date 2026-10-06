from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.contact_service import submit_contact_message

router = APIRouter(prefix="/api/v1/contact", tags=["contact"])


class ContactRequest(BaseModel):
    full_name: str
    phone: str
    email: str | None = None
    message: str
    product_interest: str | None = None
    # Optional - set when the request is about a specific product category
    # (e.g. "medical"), so the CRM lead is tagged with it.


@router.post("")
async def submit_contact(payload: ContactRequest, db: AsyncSession = Depends(get_db)):
    return await submit_contact_message(db, payload.full_name, payload.phone, payload.email, payload.message, payload.product_interest)
