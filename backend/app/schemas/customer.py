import uuid
from datetime import datetime

from pydantic import BaseModel


class CustomerContactOut(BaseModel):
    id: uuid.UUID
    label: str
    full_name: str
    phone: str | None
    email: str | None

    model_config = {"from_attributes": True}


class CustomerContactCreate(BaseModel):
    label: str
    full_name: str
    phone: str | None = None
    email: str | None = None


class CommunicationOut(BaseModel):
    id: uuid.UUID
    channel: str
    direction: str
    subject: str | None
    body: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CustomerDetailOut(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str | None
    phone: str
    id_number: str | None
    kra_pin: str | None
    lead_source: str | None
    consent_marketing: bool
    created_at: datetime
    contacts: list[CustomerContactOut]
    communications: list[CommunicationOut]
