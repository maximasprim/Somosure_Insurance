import uuid
from datetime import date, datetime

from pydantic import BaseModel


class ClaimReportRequest(BaseModel):
    policy_id: str
    customer_id: str
    incident_date: date
    incident_description: str
    incident_location: str | None = None


class ClaimDocumentOut(BaseModel):
    id: uuid.UUID
    document_type: str
    original_filename: str
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class ClaimOut(BaseModel):
    id: uuid.UUID
    reference: str
    policy_id: uuid.UUID
    status: str
    incident_date: date
    incident_description: str
    incident_location: str | None
    provider_reference: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ClaimEventOut(BaseModel):
    id: uuid.UUID
    event_type: str
    from_status: str | None
    to_status: str | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ClaimTransitionRequest(BaseModel):
    to_status: str
    notes: str | None = None
