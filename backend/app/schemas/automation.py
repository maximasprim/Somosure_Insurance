import uuid
from datetime import datetime

from pydantic import BaseModel


class AutomationRuleCreate(BaseModel):
    name: str
    trigger_event: str
    conditions: dict = {}
    action_type: str
    action_config: dict = {}
    delay_seconds: int = 0
    is_active: bool = True


class AutomationRuleUpdate(BaseModel):
    is_active: bool | None = None
    conditions: dict | None = None
    action_config: dict | None = None
    delay_seconds: int | None = None


class AutomationRuleOut(BaseModel):
    id: uuid.UUID
    name: str
    trigger_event: str
    conditions: dict
    action_type: str
    action_config: dict
    delay_seconds: int
    is_active: bool

    model_config = {"from_attributes": True}


class AutomationRunOut(BaseModel):
    id: uuid.UUID
    rule_id: uuid.UUID
    trigger_event: str
    entity_type: str
    entity_id: str
    status: str
    scheduled_for: datetime
    executed_at: datetime | None
    result: dict
    error: str | None

    model_config = {"from_attributes": True}


class StickerOut(BaseModel):
    id: uuid.UUID
    reference: str
    policy_id: uuid.UUID
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StickerAdvanceRequest(BaseModel):
    to_status: str
    notes: str | None = None


class NotificationOut(BaseModel):
    id: uuid.UUID
    channel: str
    event_type: str
    subject: str | None
    body: str
    status: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}
