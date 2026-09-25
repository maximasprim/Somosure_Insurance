import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RoleOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None

    model_config = {"from_attributes": True}


class StaffUserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    phone: str | None
    full_name: str
    role: str
    is_active: bool
    created_at: datetime


class StaffUserCreate(BaseModel):
    email: EmailStr
    phone: str | None = None
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: str


class StaffUserUpdate(BaseModel):
    full_name: str | None = None
    is_active: bool | None = None
    role: str | None = None
