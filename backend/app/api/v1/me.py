import random
import string
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_customer
from app.models.application import Application
from app.models.claim import Claim
from app.models.customer import Customer
from app.models.notification import Notification
from app.models.payment import Payment
from app.models.policy import Policy
from app.models.support import SupportTicket
from app.schemas.application import ApplicationOut, PolicyOut
from app.schemas.automation import NotificationOut
from app.schemas.claim import ClaimOut
from app.schemas.me import (
    CustomerProfileOut,
    CustomerProfileUpdate,
    DashboardOut,
    SupportTicketCreate,
    SupportTicketOut,
)
from app.schemas.payment import PaymentOut
from app.schemas.referral import ReferralOut
from app.services.dashboard_service import get_dashboard

router = APIRouter(prefix="/api/v1/me", tags=["me"])


@router.get("", response_model=CustomerProfileOut)
async def get_profile(customer: Customer = Depends(get_current_customer)):
    return customer


@router.patch("", response_model=CustomerProfileOut)
async def update_profile(
    payload: CustomerProfileUpdate,
    customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db),
):
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)
    await db.commit()
    await db.refresh(customer)
    return customer


@router.get("/dashboard", response_model=DashboardOut)
async def dashboard(customer: Customer = Depends(get_current_customer), db: AsyncSession = Depends(get_db)):
    return await get_dashboard(db, str(customer.id))


@router.get("/policies", response_model=list[PolicyOut])
async def my_policies(customer: Customer = Depends(get_current_customer), db: AsyncSession = Depends(get_db)):
    return (await db.scalars(select(Policy).where(Policy.customer_id == customer.id))).all()


@router.get("/applications", response_model=list[ApplicationOut])
async def my_applications(customer: Customer = Depends(get_current_customer), db: AsyncSession = Depends(get_db)):
    return (await db.scalars(select(Application).where(Application.customer_id == customer.id))).all()


@router.get("/payments", response_model=list[PaymentOut])
async def my_payments(customer: Customer = Depends(get_current_customer), db: AsyncSession = Depends(get_db)):
    return (await db.scalars(select(Payment).where(Payment.customer_id == customer.id))).all()


@router.get("/claims", response_model=list[ClaimOut])
async def my_claims(customer: Customer = Depends(get_current_customer), db: AsyncSession = Depends(get_db)):
    return (
        await db.scalars(select(Claim).where(Claim.customer_id == customer.id).order_by(Claim.created_at.desc()))
    ).all()


@router.get("/referral-code", response_model=ReferralOut)
async def my_referral_code(customer: Customer = Depends(get_current_customer), db: AsyncSession = Depends(get_db)):
    from app.services.referral_service import get_or_create_referral_code

    return await get_or_create_referral_code(db, str(customer.id))


@router.post("/support-tickets", response_model=SupportTicketOut)
async def create_ticket(
    payload: SupportTicketCreate,
    customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db),
):
    reference = f"SOM-TCK-{date.today().year}-{''.join(random.choices(string.digits, k=6))}"
    ticket = SupportTicket(
        reference=reference,
        customer_id=customer.id,
        category=payload.category,
        subject=payload.subject,
        message=payload.message,
        status="open",
    )
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)
    return ticket


@router.get("/support-tickets", response_model=list[SupportTicketOut])
async def my_tickets(customer: Customer = Depends(get_current_customer), db: AsyncSession = Depends(get_db)):
    return (
        await db.scalars(
            select(SupportTicket).where(SupportTicket.customer_id == customer.id).order_by(SupportTicket.created_at.desc())
        )
    ).all()


@router.get("/notifications", response_model=list[NotificationOut])
async def my_notifications(customer: Customer = Depends(get_current_customer), db: AsyncSession = Depends(get_db)):
    return (
        await db.scalars(
            select(Notification).where(Notification.customer_id == customer.id).order_by(Notification.created_at.desc())
        )
    ).all()
