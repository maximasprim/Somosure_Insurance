import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class PolicyListOut(BaseModel):
    id: uuid.UUID
    policy_number: str
    customer_name: str
    provider_name: str
    status: str
    payment_status: str
    premium: Decimal
    start_date: date
    end_date: date
    is_mock: bool
    created_at: datetime


class PaymentListOut(BaseModel):
    id: uuid.UUID
    reference: str
    customer_name: str
    amount: Decimal
    currency: str
    method: str
    status: str
    created_at: datetime


class RenewalListOut(BaseModel):
    id: uuid.UUID
    policy_number: str
    customer_name: str
    due_date: date
    status: str
    created_at: datetime


class RenewalUpdate(BaseModel):
    status: str


class SupportTicketListOut(BaseModel):
    id: uuid.UUID
    reference: str
    customer_name: str
    category: str
    subject: str
    message: str
    status: str
    assigned_to_name: str | None
    created_at: datetime


class SupportTicketUpdate(BaseModel):
    status: str | None = None
    assigned_to_user_id: uuid.UUID | None = None


class TaskOut(BaseModel):
    id: uuid.UUID
    title: str
    lead_id: uuid.UUID | None
    assigned_to_user_id: uuid.UUID | None
    assigned_to_name: str | None
    due_at: datetime | None
    status: str
    created_at: datetime


class TaskCreate(BaseModel):
    title: str
    lead_id: uuid.UUID | None = None
    assigned_to_user_id: uuid.UUID | None = None
    due_at: datetime | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    assigned_to_user_id: uuid.UUID | None = None
    due_at: datetime | None = None
    status: str | None = None
