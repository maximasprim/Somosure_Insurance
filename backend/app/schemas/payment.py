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


class PaymentInitiateResponse(BaseModel):
    payment_id: str
    reference: str
    status: str
    provider_transaction_id: str
    is_mock: bool = True


class PaymentOut(BaseModel):
    id: uuid.UUID
    reference: str
    amount: Decimal
    currency: str
    method: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
