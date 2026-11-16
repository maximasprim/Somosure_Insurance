"""Response/request shapes for the sales-import admin endpoints."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SalesEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sheet_name: str
    sheet_year: int
    sheet_row: int | None = None
    period_year: int
    period_month: int | None = None
    client_name: str
    phone: str | None = None
    underwriter: str | None = None
    reg_no: str | None = None
    asset_ref: str | None = None
    product_line: str
    start_date: date | None = None
    expiry_date: date | None = None
    date_paid: date | None = None
    staff_name: str | None = None
    branch: str | None = None
    business_type: str | None = None
    policy_number: str | None = None
    cover_type: str | None = None
    premium: Decimal | None = None
    commission: Decimal | None = None
    wht: Decimal | None = None
    net_revenue: Decimal | None = None
    commission_rate: Decimal | None = None
    flags: list[dict[str, Any]] | None = None
    issue_level: str
    status: str
    policy_id: uuid.UUID | None = None
    overrides: dict[str, Any] | None = None


class SalesEntryPage(BaseModel):
    total: int
    premium: Decimal
    commission: Decimal
    items: list[SalesEntryOut]


class EntryOptions(BaseModel):
    years: list[int]
    underwriters: list[str]
    staff: list[str]
    branches: list[str]
    products: list[str]


class LegacyClaimOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sheet_name: str
    period_year: int
    client_name: str
    contact: str | None = None
    reg_or_policy: str | None = None
    underwriter: str | None = None
    date_reported: date | None = None
    narrative: str | None = None
    outcome: str
    milestones: list[dict[str, Any]] | None = None
    sales_entry_id: uuid.UUID | None = None
    flags: list[dict[str, Any]] | None = None
    issue_level: str
    status: str


class IpfRemittanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    period_year: int
    underwriter: str | None = None
    details: str | None = None
    date_paid: date | None = None
    amount: Decimal | None = None
    flags: list[dict[str, Any]] | None = None
    issue_level: str
    status: str


class ImportBatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str | None = None
    file_sha256: str
    status: str
    years: list[int] | None = None
    counts: dict[str, Any] | None = None
    created_at: datetime


class AliasOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    alias_key: str
    as_typed: str | None = None
    canonical: str | None = None
    branch: str | None = None
    confirmed: bool
    source: str


class AliasUpdate(BaseModel):
    canonical: str | None = Field(default=None, max_length=120)
    branch: str | None = Field(default=None, max_length=60)
    confirmed: bool = True


class AliasCreate(BaseModel):
    kind: str = Field(pattern="^(underwriter|staff)$")
    typed: str = Field(min_length=1, max_length=200)
    canonical: str | None = Field(default=None, max_length=120)
    branch: str | None = Field(default=None, max_length=60)


class FixItem(BaseModel):
    entry_id: uuid.UUID
    field: str = Field(pattern="^(start_date|expiry_date)$")
    value: date  # must equal the value the importer suggested for that row; anything else is refused


class ApplyFixes(BaseModel):
    items: list[FixItem] = Field(min_length=1, max_length=200)


# ---- the combined (platform + workbook) views --------------------------------------------------


class UnifiedSaleOut(BaseModel):
    source: str  # platform | workbook | platform+workbook
    id: str
    sold_on: date | None = None
    client_name: str | None = None
    phone: str | None = None
    underwriter: str | None = None
    reg_no: str | None = None
    product: str | None = None
    policy_number: str | None = None
    premium: Decimal | None = None
    commission: Decimal | None = None
    wht: Decimal | None = None
    net_revenue: Decimal | None = None
    staff: str | None = None
    branch: str | None = None
    business_type: str | None = None
    start_date: date | None = None
    expiry_date: date | None = None
    status: str | None = None
    customer_id: uuid.UUID | None = None


class UnifiedSalesPage(BaseModel):
    total: int
    premium: Decimal
    commission: Decimal
    items: list[UnifiedSaleOut]


class RenewalItemOut(BaseModel):
    source: str  # platform | workbook
    id: str
    expiry_date: date | None = None
    days_left: int | None = None
    client_name: str | None = None
    phone: str | None = None
    customer_id: uuid.UUID | None = None
    underwriter: str | None = None
    reg_no: str | None = None
    premium: Decimal | None = None
    staff: str | None = None
    branch: str | None = None
    status: str
    note: str | None = None
    policy_number: str | None = None


class RenewalPage(BaseModel):
    total: int
    items: list[RenewalItemOut]


class FollowUpIn(BaseModel):
    status: str | None = Field(default=None, pattern="^(contacted|quoted|renewed|lost)?$")
    note: str | None = Field(default=None, max_length=1000)


class ClientPhoneIn(BaseModel):
    client_key: str = Field(min_length=1, max_length=200)
    phone: str = Field(min_length=7, max_length=30)


class CustomerHistoryOut(BaseModel):
    entries: list[SalesEntryOut]
    claims: list[LegacyClaimOut]


class ManualSaleIn(BaseModel):
    """A sale typed into the system - the same columns as a row of the weekly sheet."""

    client_name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=30)
    customer_id: uuid.UUID | None = None  # an existing customer chosen in the form
    provider_id: uuid.UUID | None = None
    new_underwriter: str | None = Field(default=None, max_length=150)
    reg_or_product: str = Field(min_length=1, max_length=120)
    start_date: date
    expiry_date: date | None = None  # defaults to one year after the start
    date_paid: date
    staff_name: str | None = Field(default=None, max_length=80)
    branch: str | None = Field(default=None, max_length=60)
    business_type: str | None = Field(default=None, pattern="^(new_business|renewal)?$")
    policy_number: str | None = Field(default=None, max_length=80)
    cover_type: str | None = Field(default=None, max_length=30)
    premium: Decimal = Field(gt=0)
    commission: Decimal | None = Field(default=None, ge=0)
    wht: Decimal | None = Field(default=None, ge=0)
    confirm_duplicate: bool = False
