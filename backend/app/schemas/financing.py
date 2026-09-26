import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class EligibilityRequest(BaseModel):
    customer_id: str
    quote_id: str
    term_months: int = 6
    has_existing_logbook_loan: bool = False
    logbook_loan_age_months: int | None = None
    # Waives the deposit, applies the preferred interest rate, and waives
    # the three fees below - but only when has_existing_logbook_loan is
    # True AND logbook_loan_age_months is within the configured window
    # (FinancingSettings.concession_loan_age_max_months). See
    # financing_service.py.


class EligibilityOut(BaseModel):
    eligible: bool
    reason: str | None
    total_premium: Decimal
    deposit_percentage: Decimal
    deposit_amount: Decimal
    financed_amount: Decimal
    interest_rate_monthly: Decimal
    concession_applied: bool
    loan_application_fee: Decimal | None
    life_insurance_fee: Decimal | None
    excise_duty_amount: Decimal | None
    total_repayable: Decimal | None
    term_months: int
    monthly_installment: Decimal | None
    is_mock: bool


class FinancingApplicationCreate(BaseModel):
    customer_id: str
    quote_id: str
    term_months: int = 6
    has_existing_logbook_loan: bool = False
    logbook_loan_age_months: int | None = None
    is_corporate: bool = False
    # Corporate/company applicants need a certificate of incorporation
    # instead of a personal ID in the documents checklist.


class FinancingApplicationOut(BaseModel):
    id: uuid.UUID
    reference: str
    status: str
    total_premium: Decimal
    deposit_percentage: Decimal
    deposit_amount: Decimal
    financed_amount: Decimal
    interest_rate_monthly: Decimal
    concession_applied: bool
    loan_application_fee: Decimal
    life_insurance_fee: Decimal
    excise_duty_amount: Decimal
    total_repayable: Decimal
    term_months: int
    has_existing_logbook_loan: bool
    logbook_loan_age_months: int | None
    is_corporate: bool
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
    interest_rate_monthly: Decimal
    total_repayable: Decimal
    term_months: int
    monthly_installment: Decimal
    status: str
    installments: list[InstallmentOut]


class FinancingDocumentOut(BaseModel):
    id: uuid.UUID
    document_type: str
    original_filename: str
    status: str
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class FinancingEventOut(BaseModel):
    id: uuid.UUID
    event_type: str
    from_status: str | None
    to_status: str | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class FinancingTransitionRequest(BaseModel):
    to_status: str
    notes: str | None = None
    interest_rate_monthly: Decimal | None = None
    # A management-approved exception to the standard rates - only
    # honoured for staff in the "management"/"super_admin" roles, enforced
    # in the route, not here. Recalculates total_repayable and the
    # installment schedule when provided.


# --- Detail view: everything staff need on one screen to decide a
# financing application, matching the equivalent detail view built for
# insurance applications - assembled from related records rather than ORM
# relationships, per this codebase's existing convention.


class FinancingCustomerOut(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str | None
    phone: str
    id_number: str | None
    kra_pin: str | None

    model_config = {"from_attributes": True}


class FinancingQuoteOut(BaseModel):
    id: uuid.UUID
    provider_name: str
    product_name: str | None
    premium: Decimal
    total: Decimal
    currency: str


class FinancingApplicationDetailOut(BaseModel):
    id: uuid.UUID
    reference: str
    status: str
    customer: FinancingCustomerOut
    quote: FinancingQuoteOut
    total_premium: Decimal
    deposit_percentage: Decimal
    deposit_amount: Decimal
    financed_amount: Decimal
    interest_rate_monthly: Decimal
    concession_applied: bool
    loan_application_fee_pct: Decimal
    loan_application_fee: Decimal
    life_insurance_fee_pct: Decimal
    life_insurance_fee: Decimal
    excise_duty_pct: Decimal
    excise_duty_amount: Decimal
    total_repayable: Decimal
    term_months: int
    has_existing_logbook_loan: bool
    logbook_loan_age_months: int | None
    is_corporate: bool
    provider_reference: str | None
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime
    documents: list[FinancingDocumentOut]
    events: list[FinancingEventOut]
    agreement: FinancingAgreementOut | None


class FinancingSettingsOut(BaseModel):
    deposit_percentage_standard: Decimal
    interest_rate_standard_monthly: Decimal
    interest_rate_preferred_monthly: Decimal
    min_term_months: int
    max_term_months: int
    loan_application_fee_pct: Decimal
    life_insurance_fee_pct: Decimal
    excise_duty_pct: Decimal
    concession_loan_age_max_months: int
    updated_at: datetime

    model_config = {"from_attributes": True}


class FinancingSettingsUpdate(BaseModel):
    """Every field is optional - send only the ones you want to change.
    Unset fields keep their current value. Editable from the admin
    dashboard's financing settings screen."""

    deposit_percentage_standard: Decimal | None = None
    interest_rate_standard_monthly: Decimal | None = None
    interest_rate_preferred_monthly: Decimal | None = None
    min_term_months: int | None = None
    max_term_months: int | None = None
    loan_application_fee_pct: Decimal | None = None
    life_insurance_fee_pct: Decimal | None = None
    excise_duty_pct: Decimal | None = None
    concession_loan_age_max_months: int | None = None