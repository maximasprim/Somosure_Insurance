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
from app.models.rate_card import RateCardExcess, RateCardExtension, RateCardTier, RateCardVehicleClass
from app.schemas.rate_card import (
    ExcessIn,
    ExcessOut,
    ExtensionIn,
    ExtensionOut,
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
from app.services.rate_card_engine import RateCardNotConfigured, compute_motor_premium

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
    detail = VehicleClassDetailOut.model_validate(vehicle_class)
    detail.tiers = [TierOut.model_validate(t) for t in tiers]
    detail.extensions = [ExtensionOut.model_validate(e) for e in extensions]
    detail.excesses = [ExcessOut.model_validate(e) for e in excesses]
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
        "data_confidence": breakdown.data_confidence,
        "assumptions": breakdown.assumptions,
    }
