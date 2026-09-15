import uuid
from datetime import datetime

from pydantic import BaseModel


class LeadOut(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    stage: str
    source: str
    product_interest: str | None
    assigned_agent_id: uuid.UUID | None
    quote_request_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LeadWithCustomerOut(LeadOut):
    customer_name: str
    customer_phone: str


class LeadUpdate(BaseModel):
    stage: str | None = None
    assigned_agent_id: str | None = None


class LeadActivityCreate(BaseModel):
    activity_type: str
    notes: str | None = None


class LeadActivityOut(BaseModel):
    id: uuid.UUID
    activity_type: str
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class FunnelStageCount(BaseModel):
    stage: str
    count: int


class FunnelOut(BaseModel):
    stages: list[FunnelStageCount]
    total: int
