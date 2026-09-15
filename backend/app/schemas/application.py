import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class ApplicationCreate(BaseModel):
    quote_id: str
    customer_id: str
    applicant_details: dict = {}
    vehicle_id: str | None = None
    insured_asset_id: str | None = None


class ApplicationDocumentOut(BaseModel):
    id: uuid.UUID
    document_type: str
    original_filename: str
    status: str
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class ApplicationOut(BaseModel):
    id: uuid.UUID
    reference: str
    quote_id: uuid.UUID
    status: str
    provider_reference: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PolicyOut(BaseModel):
    id: uuid.UUID
    policy_number: str
    status: str
    payment_status: str
    premium: Decimal
    start_date: date
    end_date: date
    is_mock: bool

    model_config = {"from_attributes": True}
