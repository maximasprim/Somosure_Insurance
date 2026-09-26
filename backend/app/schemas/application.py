import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class ApplicationCreate(BaseModel):
    quote_id: str
    customer_id: str
    applicant_details: dict = {}
    vehicle_id: str | None = None
    insured_asset_id: str | None = None


class ApplicationDocumentOut(BaseModel):
    id: uuid.UUID
    document_type: str
    original_filename: str
    status: str
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class ApplicationOut(BaseModel):
    id: uuid.UUID
    reference: str
    quote_id: uuid.UUID
    status: str
    provider_reference: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApplicationEventOut(BaseModel):
    id: uuid.UUID
    event_type: str
    from_status: str | None
    to_status: str | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApplicationTransitionRequest(BaseModel):
    to_status: str
    notes: str | None = None


# --- Detail view: everything an underwriter needs to see on one screen to
# decide an application, assembled from the application's related records
# (customer, quote, vehicle/asset, documents, decision history) rather than
# from ORM relationships, matching how admin_records.py/admin_customers.py
# already build joined display data in this codebase.


class ApplicationCustomerOut(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str | None
    phone: str
    id_number: str | None
    kra_pin: str | None

    model_config = {"from_attributes": True}


class ApplicationVehicleOut(BaseModel):
    id: uuid.UUID
    registration_number: str
    chassis_number: str | None
    engine_number: str | None
    make: str
    model: str
    year: int
    value: Decimal
    usage: str

    model_config = {"from_attributes": True}


class ApplicationInsuredAssetOut(BaseModel):
    id: uuid.UUID
    category: str
    description: str | None
    value: Decimal | None
    details: dict

    model_config = {"from_attributes": True}


class ApplicationQuoteOut(BaseModel):
    id: uuid.UUID
    provider_name: str
    underlying_provider_name: str | None
    product_name: str | None
    premium: Decimal
    taxes: Decimal
    fees: Decimal
    total: Decimal
    currency: str
    coverage: dict
    exclusions: dict
    deductibles: dict
    is_mock: bool


class ApplicationDetailOut(BaseModel):
    id: uuid.UUID
    reference: str
    status: str
    applicant_details: dict
    provider_reference: str | None
    created_at: datetime
    updated_at: datetime
    customer: ApplicationCustomerOut
    quote: ApplicationQuoteOut
    vehicle: ApplicationVehicleOut | None
    insured_asset: ApplicationInsuredAssetOut | None
    documents: list[ApplicationDocumentOut]
    events: list[ApplicationEventOut]


class PolicyOut(BaseModel):
    id: uuid.UUID
    policy_number: str
    status: str
    payment_status: str
    premium: Decimal
    start_date: date
    end_date: date
    is_mock: bool

    model_config = {"from_attributes": True}