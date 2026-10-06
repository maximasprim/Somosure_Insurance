import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditEntryOut(BaseModel):
    id: uuid.UUID
    seq: int
    occurred_at: datetime
    kind: str
    action: str
    actor_type: str
    actor_user_id: str | None = None
    actor_name: str | None = None
    actor_email: str | None = None
    actor_role: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    entity_label: str | None = None
    related_customer_id: str | None = None
    summary: str | None = None
    reason: str | None = None
    changes: dict[str, Any] | None = None
    details: dict[str, Any] | None = None
    request_id: str | None = None
    method: str | None = None
    path: str | None = None
    status_code: int | None = None
    duration_ms: int | None = None
    ip: str | None = None
    user_agent: str | None = None

    model_config = {"from_attributes": True}


class AuditPageOut(BaseModel):
    items: list[AuditEntryOut]
    total: int
    limit: int
    offset: int


class AuditFacetsOut(BaseModel):
    entity_types: list[str]
    actions: list[str]
