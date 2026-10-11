import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.services.product_catalog import ALL_CATEGORIES

PartnerType = Literal["car_dealer", "vehicle_importer", "employer", "sme", "bank", "sacco", "agent", "corporate"]
WorkingModel = Literal["referrals", "applications", "both"]
VolumeBand = Literal["1-10", "11-50", "51-200", "200+"]

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


class PartnerApplicationIn(BaseModel):
    """What the public 'Become a partner' form sends."""

    business_name: str = Field(min_length=2, max_length=200)
    partner_type: PartnerType
    contact_name: str = Field(min_length=2, max_length=200)
    contact_email: str = Field(max_length=255)
    contact_phone: str = Field(min_length=9, max_length=30)
    town: str | None = Field(None, max_length=120)
    website: str | None = Field(None, max_length=255)
    working_model: WorkingModel
    monthly_clients: VolumeBand
    products: list[str] = Field(default_factory=list, max_length=12)
    message: str = Field(min_length=10, max_length=2000)
    # They must agree to be contacted about the application.
    consent: bool
    # Honeypot: a field real visitors never see or fill in. Bots do.
    fax: str | None = Field(None, max_length=200)

    @field_validator("business_name", "contact_name", "message", "town", "website")
    @classmethod
    def _strip(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("contact_email")
    @classmethod
    def _email(cls, value: str) -> str:
        value = value.strip().lower()
        if not _EMAIL.match(value):
            raise ValueError("Please enter a valid email address")
        return value

    @field_validator("contact_phone")
    @classmethod
    def _phone(cls, value: str) -> str:
        value = value.strip()
        if len(re.sub(r"\D", "", value)) < 9:
            raise ValueError("Please enter a valid phone number")
        return value

    @field_validator("products")
    @classmethod
    def _products(cls, value: list[str]) -> list[str]:
        unknown = [v for v in value if v not in ALL_CATEGORIES]
        if unknown:
            raise ValueError(f"Unknown product: {unknown[0]}")
        return list(dict.fromkeys(value))

    @field_validator("consent")
    @classmethod
    def _consent(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Please agree to be contacted about your application")
        return value


class PartnerApplicationReceipt(BaseModel):
    received: bool = True
    reference: str


class PartnerApplicationOut(BaseModel):
    id: uuid.UUID
    reference: str
    business_name: str
    partner_type: str
    contact_name: str
    contact_email: str
    contact_phone: str
    town: str | None
    website: str | None
    working_model: str
    monthly_clients: str
    products: list[str] | None
    message: str
    status: str
    decision_reason: str | None
    decided_at: datetime | None
    partner_id: uuid.UUID | None
    affiliate_code: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PartnerApplicationPage(BaseModel):
    items: list[PartnerApplicationOut]
    total: int
    limit: int
    offset: int
    pending_count: int


class ApproveIn(BaseModel):
    reason: str = Field(min_length=3)
    # Correct the type if the applicant chose wrongly.
    partner_type: PartnerType | None = None
    enrol_affiliate: bool = False
    # Optional special commission rate for this partner (needs enrol_affiliate).
    commission_type: Literal["percent", "fixed"] | None = None
    commission_value: Decimal | None = Field(None, ge=0, le=1_000_000)
    # Optional insurance discount credit for this partner (needs enrol_affiliate).
    discount_type: Literal["percent", "fixed"] | None = None
    discount_value: Decimal | None = Field(None, gt=0, le=10_000_000)
    discount_valid_days: int | None = Field(365, ge=1, le=3650)


class DeclineIn(BaseModel):
    reason: str = Field(min_length=3)


class ApproveOut(BaseModel):
    application: PartnerApplicationOut
    partner_id: uuid.UUID
    affiliate_code: str | None = None
    affiliate_link_path: str | None = None
    commission_rule_created: bool = False
    discount_credit_created: bool = False
    warnings: list[str] = []
