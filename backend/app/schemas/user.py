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
    must_change_password: bool = False


class StaffUserCreate(BaseModel):
    email: EmailStr
    phone: str | None = None
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: str
    # The password above is a temporary one the admin chose: make them replace it at first sign-in.
    require_password_change: bool = True


class StaffUserUpdate(BaseModel):
    """PATCH sends only what changed (exclude_unset). email and phone are new;
    the original three fields behave exactly as before."""

    full_name: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    role: str | None = None
    email: EmailStr | None = None
    # Sending phone: null clears it.
    phone: str | None = Field(default=None, max_length=30)


class StaffPasswordReset(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)
    # Make the user choose their own password at next sign-in.
    require_password_change: bool = True


class DeletionBlocker(BaseModel):
    label: str
    count: int
    # "customer": records about their customer profile; "staff": work they appear on.
    kind: str


class UserDeletionCheck(BaseModel):
    can_delete: bool
    # Plain-language reasons that stop deletion regardless of records (self, super admin).
    reasons: list[str]
    # Records that would be orphaned or lost - deactivating keeps all of them.
    blockers: list[DeletionBlocker]
    # An unused customer profile is removed together with the account.
    removes_customer_profile: bool