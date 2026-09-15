import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class ReferralOut(BaseModel):
    id: uuid.UUID
    code: str
    status: str
    reward_amount: Decimal | None
    reward_paid: bool
    created_at: datetime

    model_config = {"from_attributes": True}
