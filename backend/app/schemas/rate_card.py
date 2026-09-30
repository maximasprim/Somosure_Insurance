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
    comprehensive_ineligible_action: str = "downgrade_to_tpo"  # downgrade_to_tpo | decline
    source_document: str | None = None
    data_confidence: str = "verified"
    notes: str | None = None
    tiers: list[TierIn] = []


class VehicleClassUpdate(BaseModel):
    label: str | None = None
    min_sum_insured: Decimal | None = None
    max_vehicle_age_years: int | None = None
    comprehensive_ineligible_action: str | None = None
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
    comprehensive_ineligible_action: str
    source_document: str | None
    data_confidence: str
    notes: str | None
    is_active: bool

    model_config = {"from_attributes": True}


class VehicleClassDetailOut(VehicleClassOut):
    tiers: list[TierOut] = []
    extensions: list["ExtensionOut"] = []
    excesses: list["ExcessOut"] = []
    free_benefits: list["FreeBenefitOut"] = []


class ExtensionIn(BaseModel):
    """A priced, OPTIONAL extra benefit (courtesy car, loss of keys,
    political violence, excess protector, ...). Every field here is
    optional except code/label/basis - a broker that doesn't offer a
    given extra benefit simply never gets a row for it, which is how
    "optional depending on the broker" is expressed: nothing to disable,
    just nothing created.
    """

    vehicle_class_id: uuid.UUID | None = None  # None = provider-wide default
    code: str
    label: str
    basis: str = "percent_of_sum_insured"  # percent_of_sum_insured | flat | per_person
    rate_percent: Decimal | None = None
    flat_amount: Decimal | None = None
    min_amount: Decimal | None = None
    notes: str | None = None
    limit_amount: Decimal | None = None
    limit_label: str | None = None  # display text, e.g. "Up to KES 30,000"


class ExtensionOut(ExtensionIn):
    id: uuid.UUID
    provider_id: uuid.UUID

    model_config = {"from_attributes": True}


class FreeBenefitIn(BaseModel):
    """An included ("free") benefit shown alongside a comprehensive quote -
    windscreen, third party property damage, towing, and so on. Never
    priced. All limit fields are optional so a broker can record just a
    label with no numeric limit (e.g. "Riot and strike - Applicable").
    """

    vehicle_class_id: uuid.UUID | None = None  # None = provider-wide default
    code: str
    label: str
    limit_amount: Decimal | None = None
    limit_label: str | None = None
    top_up_note: str | None = None
    cover_type: str = "comprehensive"  # comprehensive | tpo


class FreeBenefitOut(FreeBenefitIn):
    id: uuid.UUID
    provider_id: uuid.UUID
    is_active: bool = True

    model_config = {"from_attributes": True}


class PaymentPlanIn(BaseModel):
    """One broker-configurable payment plan. See
    app/services/motor_terms.py for how a plan turns into a concrete
    payment schedule; every numeric field here is a rate-card-style input
    an admin can change without a deploy if a broker's terms change.
    """

    code: str
    label: str
    type: str = "full"  # full | installments
    enabled: bool = True
    applies_to: list[str] = ["comprehensive", "tpo"]  # which cover types this plan is offered for
    deposit_percent: Decimal | None = None  # e.g. 30 for a 30% deposit; 0/None = no deposit
    installment_options: list[int] = []  # e.g. [3, 4] - number of instalments a customer can choose between
    sticker_months_per_payment: int | None = None
    # set (e.g. 1) when each payment in this plan buys that many months of
    # sticker cover rather than the whole term up front


class PaymentPlansUpdate(BaseModel):
    plans: list[PaymentPlanIn]


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
