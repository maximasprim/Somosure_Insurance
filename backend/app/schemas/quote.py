from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class QuoteRequestCreate(BaseModel):
    category: str = Field(examples=["motor", "medical", "travel", "home", "life", "business", "personal_accident"])
    answers: dict = Field(default_factory=dict, description="Smart-form answers, shape depends on category")
    customer_id: str | None = None


class NormalizedQuoteOut(BaseModel):
    id: str
    provider_id: str
    provider_name: str
    underlying_provider_name: str | None = None
    premium: Decimal
    taxes: Decimal
    fees: Decimal
    total: Decimal
    currency: str
    coverage: dict
    exclusions: dict
    deductibles: dict
    payment_options: dict
    is_mock: bool
    valid_until: datetime | None


class QuoteRequestOut(BaseModel):
    reference: str
    category: str
    status: str
    customer_id: str | None
    quotes: list[NormalizedQuoteOut]
    note: str | None = None
