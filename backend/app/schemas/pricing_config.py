import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


# --- financing rate tiers ----------------------------------------------------------------


class RateTierBase(BaseModel):
    label: str = Field(min_length=2, max_length=80)
    applies_to: Literal["all", "individual", "corporate"] = "all"
    # From (inclusive) up to (EXCLUSIVE): back-to-back tiers meet cleanly.
    min_amount: Decimal = Field(default=Decimal("0"), ge=0)
    max_amount: Decimal | None = Field(default=None, gt=0)  # blank = no upper limit
    # Inclusive at both ends.
    min_term_months: int = Field(default=1, ge=1, le=120)
    max_term_months: int | None = Field(default=None, ge=1, le=120)  # blank = no upper limit
    interest_rate_monthly: Decimal = Field(ge=0, le=100)
    is_active: bool = True


class RateTierCreate(RateTierBase):
    pass


class RateTierUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=2, max_length=80)
    applies_to: Literal["all", "individual", "corporate"] | None = None
    min_amount: Decimal | None = Field(default=None, ge=0)
    max_amount: Decimal | None = Field(default=None, gt=0)  # send null to remove the upper limit
    min_term_months: int | None = Field(default=None, ge=1, le=120)
    max_term_months: int | None = Field(default=None, ge=1, le=120)  # send null to remove the upper limit
    interest_rate_monthly: Decimal | None = Field(default=None, ge=0, le=100)
    is_active: bool | None = None


class RateTierOut(RateTierBase):
    id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class RatePreviewOut(BaseModel):
    """Which monthly rate a loan of this size and term would get (a non-concession loan)."""

    rate: Decimal
    source: Literal["tier", "corporate", "standard"]
    tier: RateTierOut | None = None
    standard_rate: Decimal


# --- anniversary alignment ---------------------------------------------------------------------


class AnniversarySettingsOut(BaseModel):
    enabled: bool
    method: Literal["pro_rata_daily", "short_period_scale"]
    year_basis_days: int
    minimum_premium_pct: Decimal
    min_stub_days: int
    max_term_days: int
    updated_at: datetime

    model_config = {"from_attributes": True}


class AnniversarySettingsUpdate(BaseModel):
    enabled: bool | None = None
    method: Literal["pro_rata_daily", "short_period_scale"] | None = None
    year_basis_days: int | None = Field(default=None, ge=360, le=366)
    minimum_premium_pct: Decimal | None = Field(default=None, ge=0, le=100)
    min_stub_days: int | None = Field(default=None, ge=0, le=365)
    max_term_days: int | None = Field(default=None, ge=366, le=800)


class ScaleCreate(BaseModel):
    provider_id: uuid.UUID | None = None  # blank = the default table for any provider without its own
    up_to_days: int = Field(ge=1, le=800)
    percent_of_annual: Decimal = Field(ge=0, le=100)


class ScaleUpdate(BaseModel):
    up_to_days: int | None = Field(default=None, ge=1, le=800)
    percent_of_annual: Decimal | None = Field(default=None, ge=0, le=100)


class ScaleOut(BaseModel):
    id: uuid.UUID
    provider_id: uuid.UUID | None
    provider_name: str | None = None
    up_to_days: int
    percent_of_annual: Decimal


class ProviderLiteOut(BaseModel):
    id: uuid.UUID
    name: str


class PremiumPreviewOut(BaseModel):
    term_days: int
    premium: Decimal
    method_used: str
    percent_of_annual: Decimal


class SetAnniversaryRequest(BaseModel):
    anniversary_date: date  # only the month and day matter
    notes: str | None = Field(default=None, max_length=500)


class PolicyAlignmentOut(BaseModel):
    policy_id: uuid.UUID
    policy_number: str
    provider_name: str | None
    end_date: date
    annual_premium: Decimal
    strategy: str
    new_start: date
    new_end: date
    term_days: int
    stub_days: int
    very_short: bool
    note: str
    estimated_premium: Decimal
    method_used: str
    percent_of_annual: Decimal


class CustomerAnniversaryPlanOut(BaseModel):
    customer_id: uuid.UUID
    customer_name: str
    enabled: bool
    anniversary_date: date | None
    notes: str | None
    suggested_anniversary: date | None
    # True when no anniversary is saved yet and the plan below is previewing the suggestion.
    using_suggestion: bool
    policies: list[PolicyAlignmentOut]


class CustomerLookupOut(BaseModel):
    id: uuid.UUID
    full_name: str
    phone: str | None
    active_policies: int
    anniversary_date: date | None


class AnniversaryListItemOut(BaseModel):
    customer_id: uuid.UUID
    customer_name: str
    anniversary_date: date
    active_policies: int


class RenewalAlignmentOut(BaseModel):
    """Shown on the renewals screen for a customer who has a common anniversary."""

    anniversary_date: date
    strategy: str
    new_end: date
    term_days: int
    estimated_premium: Decimal
    very_short: bool
    note: str
