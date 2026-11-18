from typing import Literal

from pydantic import BaseModel, Field

Period = Field(None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="A month like 2025-01")


class AutomationSettingsIn(BaseModel):
    sheet_url: str | None = Field(None, max_length=600, description="The Google Sheet's address; empty clears it")
    enabled: bool = False
    frequency: Literal["daily", "weekly", "monthly"] = "weekly"
    weekday: int = Field(0, ge=0, le=6, description="0 = Monday (weekly)")
    day_of_month: int = Field(1, ge=1, le=28, description="Monthly: 1-28")
    hour: int = Field(6, ge=0, le=23, description="Hour of the day, Nairobi time")
    period_from: str | None = Period
    period_to: str | None = Period
    auto_post: bool = False


class RevertIn(BaseModel):
    reason: str | None = Field(None, max_length=500, description="Why - kept on the version and in the audit trail")
