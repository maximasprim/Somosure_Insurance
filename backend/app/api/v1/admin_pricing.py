"""Admin endpoints for the two pricing features that staff configure:

  * Bidii Credit IPF rate tiers (the monthly rate by loan amount and term);
  * anniversary alignment (one renewal date for all of a customer's covers) and the
    short-period premium rules behind it.

Configuration needs a finance/management role; looking up a customer's alignment plan
is open to the roles that handle renewals.
"""

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_claims, require_roles
from app.schemas.pricing_config import (
    AnniversaryListItemOut,
    AnniversarySettingsOut,
    AnniversarySettingsUpdate,
    CustomerAnniversaryPlanOut,
    CustomerLookupOut,
    PremiumPreviewOut,
    ProviderLiteOut,
    RatePreviewOut,
    RateTierCreate,
    RateTierOut,
    RateTierUpdate,
    ScaleCreate,
    ScaleOut,
    ScaleUpdate,
    SetAnniversaryRequest,
)
from app.services import anniversary_service, rate_tier_service

CONFIG_ROLES = ("super_admin", "finance_officer", "management")
PLAN_ROLES = ("super_admin", "management", "operations", "sales_agent", "finance_officer")

tiers_router = APIRouter(
    prefix="/api/v1/admin/financing/rate-tiers",
    tags=["financing-rate-tiers"],
    dependencies=[Depends(require_roles(*CONFIG_ROLES))],
)

anniversary_config_router = APIRouter(
    prefix="/api/v1/admin/anniversaries",
    tags=["anniversary-config"],
    dependencies=[Depends(require_roles(*CONFIG_ROLES))],
)

anniversary_plan_router = APIRouter(
    prefix="/api/v1/admin/anniversaries",
    tags=["anniversary-plans"],
    dependencies=[Depends(require_roles(*PLAN_ROLES))],
)


# --- financing rate tiers ---------------------------------------------------------------------


@tiers_router.get("", response_model=list[RateTierOut])
async def list_tiers(db: AsyncSession = Depends(get_db)):
    return await rate_tier_service.list_tiers(db)


@tiers_router.get("/preview", response_model=RatePreviewOut)
async def preview_rate(
    amount: Decimal = Query(gt=0),
    term_months: int = Query(ge=1, le=120),
    corporate: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """Which rate a loan of this size and term would get, and from where. A test tool."""
    return await rate_tier_service.preview_rate(db, amount, term_months, corporate)


@tiers_router.post("", response_model=RateTierOut, status_code=status.HTTP_201_CREATED)
async def create_tier(payload: RateTierCreate, db: AsyncSession = Depends(get_db)):
    return await rate_tier_service.create_tier(db, payload)


@tiers_router.patch("/{tier_id}", response_model=RateTierOut)
async def update_tier(tier_id: uuid.UUID, payload: RateTierUpdate, db: AsyncSession = Depends(get_db)):
    return await rate_tier_service.update_tier(db, tier_id, payload)


@tiers_router.delete("/{tier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tier(tier_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await rate_tier_service.delete_tier(db, tier_id)


# --- anniversary configuration ----------------------------------------------------------------------


@anniversary_config_router.get("/settings", response_model=AnniversarySettingsOut)
async def get_settings(db: AsyncSession = Depends(get_db)):
    return await anniversary_service.get_settings(db)


@anniversary_config_router.patch("/settings", response_model=AnniversarySettingsOut)
async def update_settings(
    payload: AnniversarySettingsUpdate, db: AsyncSession = Depends(get_db), claims: dict = Depends(get_current_claims)
):
    return await anniversary_service.update_settings(db, payload, claims.get("sub"))


@anniversary_config_router.get("/providers", response_model=list[ProviderLiteOut])
async def list_providers(db: AsyncSession = Depends(get_db)):
    return await anniversary_service.providers_lite(db)


@anniversary_config_router.get("/scales", response_model=list[ScaleOut])
async def list_scales(db: AsyncSession = Depends(get_db)):
    return await anniversary_service.list_scales(db)


@anniversary_config_router.post("/scales", response_model=ScaleOut, status_code=status.HTTP_201_CREATED)
async def create_scale(payload: ScaleCreate, db: AsyncSession = Depends(get_db)):
    return await anniversary_service.create_scale(db, payload)


@anniversary_config_router.patch("/scales/{scale_id}", response_model=ScaleOut)
async def update_scale(scale_id: uuid.UUID, payload: ScaleUpdate, db: AsyncSession = Depends(get_db)):
    return await anniversary_service.update_scale(db, scale_id, payload)


@anniversary_config_router.delete("/scales/{scale_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scale(scale_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await anniversary_service.delete_scale(db, scale_id)


@anniversary_config_router.get("/preview", response_model=PremiumPreviewOut)
async def preview_premium(
    annual_premium: Decimal = Query(gt=0),
    term_days: int = Query(ge=1, le=800),
    provider_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    """What the configured short-period rules would charge for a cover of this length."""
    return await anniversary_service.preview_premium(db, annual_premium, term_days, provider_id)


# --- a customer's alignment ------------------------------------------------------------------------------


@anniversary_plan_router.get("", response_model=list[AnniversaryListItemOut])
async def list_anniversaries(db: AsyncSession = Depends(get_db)):
    """Customers who have a common anniversary set."""
    return await anniversary_service.list_anniversaries(db)


@anniversary_plan_router.get("/customers", response_model=list[CustomerLookupOut])
async def find_customers(search: str = Query(min_length=2, max_length=60), db: AsyncSession = Depends(get_db)):
    return await anniversary_service.lookup_customers(db, search)


@anniversary_plan_router.get("/customers/{customer_id}", response_model=CustomerAnniversaryPlanOut)
async def get_plan(customer_id: uuid.UUID, preview_date: date | None = None, db: AsyncSession = Depends(get_db)):
    """The customer's active policies with how each would be renewed to reach their
    anniversary. Without a saved anniversary it previews the suggested one (or `preview_date`)."""
    return await anniversary_service.customer_plan(db, customer_id, preview_date)


@anniversary_plan_router.put("/customers/{customer_id}", response_model=CustomerAnniversaryPlanOut)
async def set_anniversary(
    customer_id: uuid.UUID,
    payload: SetAnniversaryRequest,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(get_current_claims),
):
    await anniversary_service.set_customer_anniversary(db, customer_id, payload.anniversary_date, payload.notes, claims.get("sub"))
    return await anniversary_service.customer_plan(db, customer_id)


@anniversary_plan_router.delete("/customers/{customer_id}", response_model=CustomerAnniversaryPlanOut)
async def clear_anniversary(customer_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await anniversary_service.clear_customer_anniversary(db, customer_id)
    return await anniversary_service.customer_plan(db, customer_id)
