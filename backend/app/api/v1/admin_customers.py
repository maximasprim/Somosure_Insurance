import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_roles
from app.models.crm import Communication
from app.models.customer import Customer, CustomerContact
from app.schemas.customer import CustomerContactCreate, CustomerContactOut, CustomerDetailOut

router = APIRouter(
    prefix="/api/v1/admin/customers",
    tags=["admin-customers"],
    dependencies=[
        Depends(require_roles("super_admin", "operations", "management", "sales_agent", "customer_support", "claims_officer"))
    ],
)


@router.get("/{customer_id}", response_model=CustomerDetailOut)
async def get_customer(customer_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")

    contacts = (
        await db.scalars(select(CustomerContact).where(CustomerContact.customer_id == customer_id))
    ).all()
    communications = (
        await db.scalars(
            select(Communication).where(Communication.customer_id == customer_id).order_by(Communication.created_at.desc())
        )
    ).all()

    return CustomerDetailOut(
        id=customer.id,
        full_name=customer.full_name,
        email=customer.email,
        phone=customer.phone,
        id_number=customer.id_number,
        kra_pin=customer.kra_pin,
        lead_source=customer.lead_source,
        consent_marketing=customer.consent_marketing,
        created_at=customer.created_at,
        contacts=contacts,
        communications=communications,
    )


@router.post("/{customer_id}/contacts", response_model=CustomerContactOut, status_code=status.HTTP_201_CREATED)
async def add_customer_contact(customer_id: uuid.UUID, payload: CustomerContactCreate, db: AsyncSession = Depends(get_db)):
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")

    contact = CustomerContact(id=uuid.uuid4(), customer_id=customer_id, **payload.model_dump())
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return contact


@router.delete("/{customer_id}/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer_contact(customer_id: uuid.UUID, contact_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    contact = await db.get(CustomerContact, contact_id)
    if not contact or contact.customer_id != customer_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contact not found")
    await db.delete(contact)
    await db.commit()
