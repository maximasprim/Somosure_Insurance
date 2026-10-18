import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


# --- loan officers --------------------------------------------------------------------


class LoanOfficerCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    staff_number: str = Field(min_length=2, max_length=40)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=30)
    monthly_target: Decimal | None = Field(default=None, ge=0)


class LoanOfficerUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=30)
    monthly_target: Decimal | None = Field(default=None, ge=0)
    is_active: bool | None = None


class LoanOfficerOut(BaseModel):
    id: uuid.UUID
    full_name: str
    staff_number: str
    email: str | None
    phone: str | None
    monthly_target: Decimal | None
    is_active: bool

    model_config = {"from_attributes": True}


class LoanOfficerSummaryOut(LoanOfficerOut):
    """An officer with this month's results and what they have earned."""

    financed_this_month: Decimal
    requests_this_month: int
    target_progress_pct: float | None
    commission_pending: Decimal
    commission_approved: Decimal
    commission_paid: Decimal


class OfficerCommissionOut(BaseModel):
    id: uuid.UUID
    loan_officer_id: uuid.UUID
    loan_officer_name: str | None = None
    financing_application_id: uuid.UUID
    financing_reference: str | None = None
    policy_id: uuid.UUID | None
    policy_number: str | None = None
    somosure_net_commission: Decimal | None
    rate_pct: Decimal
    commission_amount: Decimal | None
    status: str
    approved_at: datetime | None
    paid_at: datetime | None
    payout_reference: str | None
    created_at: datetime


class CommissionBasisRequest(BaseModel):
    """Somosure's net commission on the policy - the officer's share is taken from it."""

    net_commission: Decimal = Field(gt=0)


class CommissionTransitionRequest(BaseModel):
    to_status: Literal["approved", "paid", "cancelled"]
    payout_reference: str | None = Field(default=None, max_length=100)


# --- cheques ---------------------------------------------------------------------------


class ChequeCreate(BaseModel):
    cheque_number: str = Field(min_length=1, max_length=40)
    bank_name: str = Field(min_length=2, max_length=80)
    amount: Decimal = Field(gt=0)
    cheque_date: date
    notes: str | None = Field(default=None, max_length=500)


class ChequeUpdate(BaseModel):
    status: Literal["received", "banked", "bounced", "returned"] | None = None
    notes: str | None = Field(default=None, max_length=500)


class ChequeOut(BaseModel):
    id: uuid.UUID
    cheque_number: str
    bank_name: str
    amount: Decimal
    cheque_date: date
    status: str
    notes: str | None
    received_at: datetime

    model_config = {"from_attributes": True}


# --- early settlement -----------------------------------------------------------------


class SettlementQuoteOut(BaseModel):
    eligible: bool
    reason: str | None = None
    instalments_remaining: int = 0
    outstanding_principal: Decimal = Decimal("0.00")
    fee_pct: Decimal = Decimal("0.00")
    fee_amount: Decimal = Decimal("0.00")
    total_due: Decimal = Decimal("0.00")
    would_have_paid: Decimal = Decimal("0.00")
    saving: Decimal = Decimal("0.00")
    capped: bool = False


class SettleRequest(BaseModel):
    payment_reference: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=500)


class SettlementOut(BaseModel):
    id: uuid.UUID
    instalments_remaining: int
    outstanding_principal: Decimal
    fee_pct: Decimal
    fee_amount: Decimal
    total_paid: Decimal
    would_have_paid: Decimal
    payment_reference: str | None
    notes: str | None
    settled_at: datetime

    model_config = {"from_attributes": True}


# --- the per-application IPF panel ------------------------------------------------------


class TrackerOut(BaseModel):
    required: bool
    installed: bool
    provider: str | None
    device_id: str | None
    installed_at: datetime | None


class IpfDetailOut(BaseModel):
    ipf_type: str
    loan_officer: LoanOfficerOut | None
    commission: OfficerCommissionOut | None
    tracker: TrackerOut
    original_logbook_received_at: datetime | None
    cheques_required: int
    cheques_received: int
    cheques: list[ChequeOut]
    early_settlement: SettlementQuoteOut | None
    settlement: SettlementOut | None


class IpfTypeRequest(BaseModel):
    ipf_type: Literal["linked", "unlinked"]


class AssignOfficerRequest(BaseModel):
    loan_officer_id: uuid.UUID | None = None  # null = remove the officer


class TrackerRequest(BaseModel):
    installed: bool
    provider: str | None = Field(default=None, max_length=80)
    device_id: str | None = Field(default=None, max_length=80)


class LogbookRequest(BaseModel):
    received: bool
