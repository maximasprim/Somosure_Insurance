import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class PaymentInitiateRequest(BaseModel):
    application_id: str
    customer_id: str
    amount: Decimal
    phone: str | None = None
    method: str = "mpesa"
    plan_code: str | None = None
    # Set together with `installments` to pay against one of the quote's
    # configured payment plans (see app/services/motor_terms.py) instead
    # of paying `amount` in full. When set, the amount actually charged
    # is looked up from the quote's own stored plan options - not taken
    # from `amount` - so the client can't under- or over-state what's due
    # for this leg. Leave both unset for the original "pay in full" flow.
    installments: int | None = None


class PaymentInitiateResponse(BaseModel):
    payment_id: str
    reference: str
    status: str
    provider_transaction_id: str
    is_mock: bool = True
    plan_code: str | None = None
    installment_sequence: int | None = None
    remaining_schedule: list[dict] | None = None
    # The not-yet-paid legs of this plan, if any - so the frontend can
    # show "next payment: KES X due <date>" without re-fetching the quote.


class PaymentOut(BaseModel):
    id: uuid.UUID
    reference: str
    amount: Decimal
    currency: str
    method: str
    status: str
    plan_code: str | None = None
    installment_sequence: int | None = None
    total_amount: Decimal | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class NextInstallmentRequest(BaseModel):
    phone: str | None = None
