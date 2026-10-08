import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class AffiliateSettingsOut(BaseModel):
    program_enabled: bool
    default_rate_type: str
    default_rate_value: Decimal
    min_premium: Decimal | None
    max_commission_per_policy: Decimal | None
    scope: str
    window_months: int
    auto_approve: bool
    allow_self_enrollment: bool
    updated_at: datetime

    model_config = {"from_attributes": True}


class AffiliateSettingsUpdate(BaseModel):
    program_enabled: bool | None = None
    default_rate_type: Literal["percent", "fixed"] | None = None
    default_rate_value: Decimal | None = Field(None, ge=0, le=1_000_000)
    min_premium: Decimal | None = Field(None, ge=0)
    max_commission_per_policy: Decimal | None = Field(None, ge=0)
    scope: Literal["first_policy", "all_policies"] | None = None
    window_months: int | None = Field(None, ge=1, le=120)
    auto_approve: bool | None = None
    allow_self_enrollment: bool | None = None


class RateRuleIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    rate_type: Literal["percent", "fixed"] = "percent"
    rate_value: Decimal = Field(ge=0, le=1_000_000)
    max_amount: Decimal | None = Field(None, ge=0)
    affiliate_customer_id: uuid.UUID | None = None
    category: str | None = Field(None, max_length=50)
    starts_on: date | None = None
    ends_on: date | None = None
    active: bool = True


class RateRuleUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=120)
    rate_type: Literal["percent", "fixed"] | None = None
    rate_value: Decimal | None = Field(None, ge=0, le=1_000_000)
    max_amount: Decimal | None = Field(None, ge=0)
    affiliate_customer_id: uuid.UUID | None = None
    category: str | None = Field(None, max_length=50)
    starts_on: date | None = None
    ends_on: date | None = None
    active: bool | None = None


class RateRuleOut(BaseModel):
    id: uuid.UUID
    name: str
    rate_type: str
    rate_value: Decimal
    max_amount: Decimal | None
    affiliate_customer_id: uuid.UUID | None
    affiliate_name: str | None = None
    category: str | None
    starts_on: date | None
    ends_on: date | None
    active: bool
    created_at: datetime


class EnrollIn(BaseModel):
    customer_id: uuid.UUID | None = None
    email: str | None = None
    phone: str | None = None
    notes: str | None = None


class AffiliateUpdate(BaseModel):
    status: Literal["active", "suspended"] | None = None
    payout_phone: str | None = Field(None, max_length=20)
    notes: str | None = None


class AffiliateOut(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    customer_name: str | None = None
    customer_phone: str | None = None
    code: str
    status: str
    payout_method: str
    payout_phone: str | None
    notes: str | None
    referred: int = 0
    converted: int = 0
    earned_pending: Decimal = Decimal("0")
    earned_approved: Decimal = Decimal("0")
    earned_paid: Decimal = Decimal("0")
    created_at: datetime


class CommissionOut(BaseModel):
    id: uuid.UUID
    referrer_customer_id: uuid.UUID
    referrer_name: str | None = None
    referrer_phone: str | None = None
    payout_phone: str | None = None
    referred_name: str | None = None
    policy_id: uuid.UUID | None
    policy_number: str | None = None
    category: str | None
    premium: Decimal
    rate_type: str
    rate_value: Decimal
    rate_label: str | None
    commission_amount: Decimal
    status: str
    status_note: str | None
    approved_at: datetime | None
    paid_at: datetime | None
    payout_method: str | None
    payout_reference: str | None
    created_at: datetime


class CommissionPage(BaseModel):
    items: list[CommissionOut]
    total: int
    limit: int
    offset: int


class ReasonIn(BaseModel):
    reason: str | None = None


class PayIn(BaseModel):
    payout_reference: str
    payout_method: str | None = "mpesa"


class BulkIn(BaseModel):
    action: Literal["approve", "pay"]
    ids: list[uuid.UUID] = Field(min_length=1, max_length=200)
    payout_reference: str | None = None
    payout_method: str | None = "mpesa"


class BulkResult(BaseModel):
    done: int
    failed: list[dict]


class SummaryOut(BaseModel):
    pending_count: int
    pending_amount: Decimal
    approved_count: int
    approved_amount: Decimal
    paid_count: int
    paid_amount: Decimal
    affiliates: int
    referred: int
    converted: int


class MyCommissionOut(BaseModel):
    id: uuid.UUID
    category: str | None
    referred_first_name: str | None
    commission_amount: Decimal
    status: str
    created_at: datetime
    paid_at: datetime | None


class MyAffiliateOut(BaseModel):
    program_enabled: bool
    can_self_enroll: bool
    is_affiliate: bool
    affiliate_code: str | None = None
    affiliate_status: str | None = None
    payout_phone: str | None = None
    referred: int
    converted: int
    earned_pending: Decimal
    earned_approved: Decimal
    earned_paid: Decimal
    commissions: list[MyCommissionOut]


class MyAffiliateUpdate(BaseModel):
    payout_phone: str = Field(min_length=9, max_length=20)
