import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class EligibilityRequest(BaseModel):
    customer_id: str
    quote_id: str
    term_months: int = 6


class EligibilityOut(BaseModel):
    eligible: bool
    reason: str | None
    total_premium: Decimal
    deposit_percentage: Decimal
    deposit_amount: Decimal
    financed_amount: Decimal
    term_months: int
    monthly_installment: Decimal | None
    is_mock: bool


class FinancingApplicationCreate(BaseModel):
    customer_id: str
    quote_id: str
    term_months: int = 6


class FinancingApplicationOut(BaseModel):
    id: uuid.UUID
    reference: str
    status: str
    total_premium: Decimal
    deposit_amount: Decimal
    financed_amount: Decimal
    term_months: int
    provider_reference: str | None
    rejection_reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class InstallmentOut(BaseModel):
    id: uuid.UUID
    installment_number: int
    due_date: date
    amount: Decimal
    status: str
    paid_at: datetime | None

    model_config = {"from_attributes": True}


class FinancingAgreementOut(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    financed_amount: Decimal
    term_months: int
    monthly_installment: Decimal
    status: str
    installments: list[InstallmentOut]
