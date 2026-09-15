import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.schemas.application import ApplicationOut, PolicyOut
from app.schemas.payment import PaymentOut
from app.schemas.quote import QuoteRequestOut


class CustomerProfileOut(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str | None
    phone: str
    id_number: str | None
    kra_pin: str | None
    consent_marketing: bool

    model_config = {"from_attributes": True}


class CustomerProfileUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    id_number: str | None = None
    kra_pin: str | None = None
    consent_marketing: bool | None = None


class DashboardOut(BaseModel):
    active_policies: list[PolicyOut]
    pending_applications: list[ApplicationOut]
    upcoming_renewals: list[PolicyOut]
    outstanding_payments: list[PaymentOut]


class SupportTicketCreate(BaseModel):
    category: str
    subject: str
    message: str


class SupportTicketOut(BaseModel):
    id: uuid.UUID
    reference: str
    category: str
    subject: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
