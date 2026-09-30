"""Admin CRUD for the configurable rate-card engine (app/models/rate_card.py).

This is the "configure rates from the backend, add new brokers" surface
the platform owner asked for: every number RateCardAdapter prices off is
editable here, and a brand-new broker is just a POST to /providers
followed by classes/tiers/extensions for it - no code deploy needed.
See docs/RATE_CARDS.md for the canonical vehicle-class codes and the
shape of a tier.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_roles
from app.models.provider import InsuranceProvider
from app.models.rate_card import RateCardExcess, RateCardExtension, RateCardFreeBenefit, RateCardTier, RateCardVehicleClass
from app.schemas.rate_card import (
    ExcessIn,
    ExcessOut,
    ExtensionIn,
    ExtensionOut,
    FreeBenefitIn,
    FreeBenefitOut,
    PaymentPlanIn,
    PaymentPlansUpdate,
    RateCardProviderCreate,
    RateCardProviderOut,
    RateCardQuotePreviewRequest,
    TierIn,
    TierOut,
    VehicleClassCreate,
    VehicleClassDetailOut,
    VehicleClassOut,
    VehicleClassUpdate,
)
from app.services import motor_terms
from app.services.rate_card_engine import RateCardIneligible, RateCardNotConfigured, compute_motor_premium

router = APIRouter(
    prefix="/api/v1/admin/rate-cards",
    tags=["admin-rate-cards"],
    dependencies=[Depends(require_roles("super_admin", "operations", "management", "underwriter"))],
)


async def _get_provider_or_404(db: AsyncSession, provider_id: str) -> InsuranceProvider:
    provider = await db.get(InsuranceProvider, provider_id)
    if not provider:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Provider not found")
    return provider


async def _get_class_or_404(db: AsyncSession, class_id: str) -> RateCardVehicleClass:
    vehicle_class = await db.get(RateCardVehicleClass, class_id)
    if not vehicle_class:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vehicle class not found")
    return vehicle_class


# --- Providers -----------------------------------------------------------


@router.get("/providers", response_model=list[RateCardProviderOut])
async def list_rate_card_providers(db: AsyncSession = Depends(get_db)):
    return (
        await db.scalars(select(InsuranceProvider).where(InsuranceProvider.integration_mode == "rate_card"))
    ).all()


@router.post("/providers", response_model=RateCardProviderOut, status_code=status.HTTP_201_CREATED)
async def create_rate_card_provider(payload: RateCardProviderCreate, db: AsyncSession = Depends(get_db)):
    """Onboards a brand-new broker. Starts inactive (status="inactive")
    so it never appears in a customer's comparison table until an admin
    has added at least one vehicle class and flipped it active - the same
    "seed as inactive, activate once ready" pattern already used for the
    pending real-insurer rows in app/db/seed.py.
    """
    existing = await db.scalar(select(InsuranceProvider).where(InsuranceProvider.name == payload.name))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "A provider with this name already exists")

    provider = InsuranceProvider(
        id=uuid.uuid4(),
        name=payload.name,
        provider_type=payload.provider_type,
        integration_mode="rate_card",
        status="inactive",
        supports_quote=True,
        integration_version="rate-card-1.0",
    )
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    return provider


@router.post("/providers/{provider_id}/activate", response_model=RateCardProviderOut)
async def activate_rate_card_provider(provider_id: str, db: AsyncSession = Depends(get_db)):
    provider = await _get_provider_or_404(db, provider_id)
    has_class = await db.scalar(
        select(RateCardVehicleClass).where(RateCardVehicleClass.provider_id == provider.id)
    )
    if not has_class:
        raise HTTPException(status.HTTP_409_CONFLICT, "Add at least one vehicle class before activating this provider")
    provider.status = "active"
    await db.commit()
    await db.refresh(provider)
    return provider


# --- Vehicle classes -------------------------------------------------------


@router.get("/providers/{provider_id}/classes", response_model=list[VehicleClassOut])
async def list_vehicle_classes(provider_id: str, db: AsyncSession = Depends(get_db)):
    await _get_provider_or_404(db, provider_id)
    return (
        await db.scalars(select(RateCardVehicleClass).where(RateCardVehicleClass.provider_id == provider_id))
    ).all()


@router.post("/providers/{provider_id}/classes", response_model=VehicleClassDetailOut, status_code=status.HTTP_201_CREATED)
async def create_vehicle_class(provider_id: str, payload: VehicleClassCreate, db: AsyncSession = Depends(get_db)):
    provider = await _get_provider_or_404(db, provider_id)
    existing = await db.scalar(
        select(RateCardVehicleClass).where(
            RateCardVehicleClass.provider_id == provider.id, RateCardVehicleClass.code == payload.code
        )
    )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, f"'{payload.code}' already exists for this provider")

    vehicle_class = RateCardVehicleClass(
        id=uuid.uuid4(),
        provider_id=provider.id,
        **payload.model_dump(exclude={"tiers"}),
    )
    db.add(vehicle_class)
    await db.flush()

    for tier_payload in payload.tiers:
        db.add(RateCardTier(id=uuid.uuid4(), vehicle_class_id=vehicle_class.id, **tier_payload.model_dump()))

    await db.commit()
    return await _load_class_detail(db, vehicle_class.id)


async def _load_class_detail(db: AsyncSession, class_id) -> RateCardVehicleClass:
    vehicle_class = await _get_class_or_404(db, str(class_id))
    tiers = (
        await db.scalars(
            select(RateCardTier).where(RateCardTier.vehicle_class_id == vehicle_class.id).order_by(RateCardTier.tier_order)
        )
    ).all()
    extensions = (
        await db.scalars(select(RateCardExtension).where(RateCardExtension.vehicle_class_id == vehicle_class.id))
    ).all()
    excesses = (
        await db.scalars(select(RateCardExcess).where(RateCardExcess.vehicle_class_id == vehicle_class.id))
    ).all()
    free_benefits = (
        await db.scalars(select(RateCardFreeBenefit).where(RateCardFreeBenefit.vehicle_class_id == vehicle_class.id))
    ).all()
    detail = VehicleClassDetailOut.model_validate(vehicle_class)
    detail.tiers = [TierOut.model_validate(t) for t in tiers]
    detail.extensions = [ExtensionOut.model_validate(e) for e in extensions]
    detail.excesses = [ExcessOut.model_validate(e) for e in excesses]
    detail.free_benefits = [FreeBenefitOut.model_validate(b) for b in free_benefits]
    return detail


@router.get("/classes/{class_id}", response_model=VehicleClassDetailOut)
async def get_vehicle_class(class_id: str, db: AsyncSession = Depends(get_db)):
    return await _load_class_detail(db, class_id)


@router.patch("/classes/{class_id}", response_model=VehicleClassDetailOut)
async def update_vehicle_class(class_id: str, payload: VehicleClassUpdate, db: AsyncSession = Depends(get_db)):
    vehicle_class = await _get_class_or_404(db, class_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(vehicle_class, field, value)
    await db.commit()
    return await _load_class_detail(db, vehicle_class.id)


# --- Tiers -----------------------------------------------------------------


@router.post("/classes/{class_id}/tiers", response_model=TierOut, status_code=status.HTTP_201_CREATED)
async def add_tier(class_id: str, payload: TierIn, db: AsyncSession = Depends(get_db)):
    await _get_class_or_404(db, class_id)
    tier = RateCardTier(id=uuid.uuid4(), vehicle_class_id=class_id, **payload.model_dump())
    db.add(tier)
    await db.commit()
    await db.refresh(tier)
    return tier


@router.patch("/tiers/{tier_id}", response_model=TierOut)
async def update_tier(tier_id: str, payload: TierIn, db: AsyncSession = Depends(get_db)):
    tier = await db.get(RateCardTier, tier_id)
    if not tier:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tier not found")
    for field, value in payload.model_dump().items():
        setattr(tier, field, value)
    await db.commit()
    await db.refresh(tier)
    return tier


@router.delete("/tiers/{tier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tier(tier_id: str, db: AsyncSession = Depends(get_db)):
    tier = await db.get(RateCardTier, tier_id)
    if not tier:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tier not found")
    await db.delete(tier)
    await db.commit()


# --- Extensions --------------------------------------------------------


@router.get("/providers/{provider_id}/extensions", response_model=list[ExtensionOut])
async def list_extensions(provider_id: str, db: AsyncSession = Depends(get_db)):
    await _get_provider_or_404(db, provider_id)
    return (await db.scalars(select(RateCardExtension).where(RateCardExtension.provider_id == provider_id))).all()


@router.post("/providers/{provider_id}/extensions", response_model=ExtensionOut, status_code=status.HTTP_201_CREATED)
async def add_extension(provider_id: str, payload: ExtensionIn, db: AsyncSession = Depends(get_db)):
    await _get_provider_or_404(db, provider_id)
    extension = RateCardExtension(id=uuid.uuid4(), provider_id=provider_id, **payload.model_dump())
    db.add(extension)
    await db.commit()
    await db.refresh(extension)
    return extension


@router.patch("/extensions/{extension_id}", response_model=ExtensionOut)
async def update_extension(extension_id: str, payload: ExtensionIn, db: AsyncSession = Depends(get_db)):
    extension = await db.get(RateCardExtension, extension_id)
    if not extension:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Extension not found")
    for field, value in payload.model_dump(exclude={"vehicle_class_id"}).items():
        setattr(extension, field, value)
    await db.commit()
    await db.refresh(extension)
    return extension


@router.delete("/extensions/{extension_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_extension(extension_id: str, db: AsyncSession = Depends(get_db)):
    extension = await db.get(RateCardExtension, extension_id)
    if not extension:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Extension not found")
    await db.delete(extension)
    await db.commit()


# --- Free (included) benefits -----------------------------------------


@router.get("/providers/{provider_id}/free-benefits", response_model=list[FreeBenefitOut])
async def list_free_benefits(provider_id: str, db: AsyncSession = Depends(get_db)):
    await _get_provider_or_404(db, provider_id)
    return (await db.scalars(select(RateCardFreeBenefit).where(RateCardFreeBenefit.provider_id == provider_id))).all()


@router.post("/providers/{provider_id}/free-benefits", response_model=FreeBenefitOut, status_code=status.HTTP_201_CREATED)
async def add_free_benefit(provider_id: str, payload: FreeBenefitIn, db: AsyncSession = Depends(get_db)):
    await _get_provider_or_404(db, provider_id)
    benefit = RateCardFreeBenefit(id=uuid.uuid4(), provider_id=provider_id, **payload.model_dump())
    db.add(benefit)
    await db.commit()
    await db.refresh(benefit)
    return benefit


@router.patch("/free-benefits/{benefit_id}", response_model=FreeBenefitOut)
async def update_free_benefit(benefit_id: str, payload: FreeBenefitIn, db: AsyncSession = Depends(get_db)):
    benefit = await db.get(RateCardFreeBenefit, benefit_id)
    if not benefit:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Free benefit not found")
    for field, value in payload.model_dump(exclude={"vehicle_class_id"}).items():
        setattr(benefit, field, value)
    await db.commit()
    await db.refresh(benefit)
    return benefit


@router.delete("/free-benefits/{benefit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_free_benefit(benefit_id: str, db: AsyncSession = Depends(get_db)):
    benefit = await db.get(RateCardFreeBenefit, benefit_id)
    if not benefit:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Free benefit not found")
    await db.delete(benefit)
    await db.commit()


# --- Payment plans -----------------------------------------------------


@router.get("/providers/{provider_id}/payment-plans", response_model=list[PaymentPlanIn])
async def get_payment_plans(provider_id: str, db: AsyncSession = Depends(get_db)):
    provider = await _get_provider_or_404(db, provider_id)
    return (provider.payment_plans or {}).get("plans") or []


@router.put("/providers/{provider_id}/payment-plans", response_model=list[PaymentPlanIn])
async def set_payment_plans(provider_id: str, payload: PaymentPlansUpdate, db: AsyncSession = Depends(get_db)):
    """Replaces this broker's whole payment-plan catalog in one call -
    plans are small and edited together, so there's no per-plan CRUD.
    Applies to every rate-card motor quote from this broker from the next
    quote request onward; nothing already quoted or paid is affected."""
    provider = await _get_provider_or_404(db, provider_id)
    provider.payment_plans = {"plans": [p.model_dump() for p in payload.plans]}
    await db.commit()
    return payload.plans


@router.post("/providers/{provider_id}/payment-plans/apply-template", response_model=list[PaymentPlanIn])
async def apply_payment_plan_template(provider_id: str, db: AsyncSession = Depends(get_db)):
    """Pre-fills this broker with a typical starter set of plans (pay in
    full; 30% deposit + 3 or 4 monthly instalments; straight monthly with
    a one-month sticker per payment) so an admin onboarding a new broker
    doesn't have to type the shape out by hand - every figure is then
    editable via PUT .../payment-plans as usual."""
    provider = await _get_provider_or_404(db, provider_id)
    plans = motor_terms.starter_template()["payment_plans"]
    provider.payment_plans = {"plans": plans}
    await db.commit()
    return plans


# --- Starter catalog (for onboarding a new broker) ----------------------


@router.get("/starter-template")
async def get_starter_template():
    """The full suggested starting point for a new broker's motor terms -
    eligibility defaults, payment plans, and the standard catalog of free
    and extra-benefit codes (see app/services/motor_terms.py) - so the
    admin UI can pre-fill a new broker's setup form. Nothing here is
    applied to any provider until the admin saves it against one.
    """
    return motor_terms.starter_template()


# --- Excesses ------------------------------------------------------------


@router.post("/classes/{class_id}/excesses", response_model=ExcessOut, status_code=status.HTTP_201_CREATED)
async def add_excess(class_id: str, payload: ExcessIn, db: AsyncSession = Depends(get_db)):
    vehicle_class = await _get_class_or_404(db, class_id)
    excess = RateCardExcess(
        id=uuid.uuid4(), provider_id=vehicle_class.provider_id, **payload.model_dump(exclude={"vehicle_class_id"}),
        vehicle_class_id=vehicle_class.id,
    )
    db.add(excess)
    await db.commit()
    await db.refresh(excess)
    return excess


@router.delete("/excesses/{excess_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_excess(excess_id: str, db: AsyncSession = Depends(get_db)):
    excess = await db.get(RateCardExcess, excess_id)
    if not excess:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Excess not found")
    await db.delete(excess)
    await db.commit()


# --- Live preview ----------------------------------------------------------


@router.post("/providers/{provider_id}/preview")
async def preview_quote(provider_id: str, payload: RateCardQuotePreviewRequest, db: AsyncSession = Depends(get_db)):
    """Runs the same pricing logic a real customer quote would, so an
    admin can sanity-check a tier/extension edit immediately instead of
    running a full quote request end to end."""
    await _get_provider_or_404(db, provider_id)
    try:
        breakdown = await compute_motor_premium(db, provider_id, payload.answers)
    except RateCardIneligible as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "; ".join(exc.reasons)) from exc
    except RateCardNotConfigured as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    return {
        "vehicle_class_label": breakdown.vehicle_class_label,
        "cover_type": breakdown.cover_type,
        "base_premium": str(breakdown.base_premium),
        "extensions": breakdown.extensions,
        "extensions_total": str(breakdown.extensions_total),
        "phcf": str(breakdown.phcf),
        "training_levy": str(breakdown.training_levy),
        "stamp_duty": str(breakdown.stamp_duty),
        "total": str(breakdown.total),
        "free_benefits": breakdown.free_benefits,
        "payment_plans": breakdown.payment_plans,
        "data_confidence": breakdown.data_confidence,
        "assumptions": breakdown.assumptions,
    }
