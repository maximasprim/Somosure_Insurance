import uuid
from decimal import Decimal

from pydantic import BaseModel


class RateCardProviderCreate(BaseModel):
    """Creates a brand-new rate-card-backed broker in one call: the
    InsuranceProvider row plus nothing else - classes/tiers/extensions are
    added afterwards against the returned provider_id. This is the "add a
    new broker" entry point: no code change is needed to bring on a
    broker whose rates you've just been given, only these admin calls.
    """

    name: str
    provider_type: str = "insurer"


class RateCardProviderOut(BaseModel):
    id: uuid.UUID
    name: str
    provider_type: str
    status: str
    integration_mode: str

    model_config = {"from_attributes": True}


class TierIn(BaseModel):
    cover_type: str  # comprehensive | tpo
    band_unit: str = "sum_insured"  # sum_insured | tonnes | passengers | subtype | none
    subtype_key: str | None = None
    min_value: Decimal | None = None
    max_value: Decimal | None = None
    rate_percent: Decimal | None = None
    flat_amount: Decimal | None = None
    min_premium: Decimal | None = None
    label: str | None = None
    tier_order: int = 0


class TierOut(TierIn):
    id: uuid.UUID
    vehicle_class_id: uuid.UUID

    model_config = {"from_attributes": True}


class VehicleClassCreate(BaseModel):
    product_category: str = "motor"
    code: str
    label: str
    min_sum_insured: Decimal | None = None
    max_vehicle_age_years: int | None = None
    source_document: str | None = None
    data_confidence: str = "verified"
    notes: str | None = None
    tiers: list[TierIn] = []


class VehicleClassUpdate(BaseModel):
    label: str | None = None
    min_sum_insured: Decimal | None = None
    max_vehicle_age_years: int | None = None
    source_document: str | None = None
    data_confidence: str | None = None
    notes: str | None = None
    is_active: bool | None = None


class VehicleClassOut(BaseModel):
    id: uuid.UUID
    provider_id: uuid.UUID
    product_category: str
    code: str
    label: str
    min_sum_insured: Decimal | None
    max_vehicle_age_years: int | None
    source_document: str | None
    data_confidence: str
    notes: str | None
    is_active: bool

    model_config = {"from_attributes": True}


class VehicleClassDetailOut(VehicleClassOut):
    tiers: list[TierOut] = []
    extensions: list["ExtensionOut"] = []
    excesses: list["ExcessOut"] = []


class ExtensionIn(BaseModel):
    vehicle_class_id: uuid.UUID | None = None  # None = provider-wide default
    code: str
    label: str
    basis: str = "percent_of_sum_insured"  # percent_of_sum_insured | flat | per_person
    rate_percent: Decimal | None = None
    flat_amount: Decimal | None = None
    min_amount: Decimal | None = None
    notes: str | None = None


class ExtensionOut(ExtensionIn):
    id: uuid.UUID
    provider_id: uuid.UUID

    model_config = {"from_attributes": True}


class ExcessIn(BaseModel):
    vehicle_class_id: uuid.UUID
    peril: str
    basis: str = "percent_of_sum_insured"
    rate_percent: Decimal | None = None
    flat_amount: Decimal | None = None
    min_amount: Decimal | None = None
    label: str | None = None


class ExcessOut(ExcessIn):
    id: uuid.UUID
    provider_id: uuid.UUID

    model_config = {"from_attributes": True}


class RateCardQuotePreviewRequest(BaseModel):
    """Lets an admin sanity-check a class/tier edit immediately, without
    running a full customer quote request end to end."""

    answers: dict


VehicleClassDetailOut.model_rebuild()
