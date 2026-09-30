import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_claims, require_roles
from app.models.application import Application
from app.models.policy import Policy
from app.models.provider import InsuranceProduct, InsuranceProductPlan, InsuranceProvider
from app.models.quote import Quote
from app.models.rate_card import RateCardExcess, RateCardExtension, RateCardFreeBenefit, RateCardTier, RateCardVehicleClass
from app.schemas.admin import ProductCreate, ProductOut, ProviderCreate, ProviderOut, ProviderUpdate
from app.services.provider_deletion import force_delete_provider
from app.schemas.application import ApplicationDetailOut, ApplicationOut, ApplicationTransitionRequest
from app.services.application_service import (
    approve_application,
    get_application_detail,
    get_application_document_url,
    transition_application,
)

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin"],
    dependencies=[Depends(require_roles("super_admin", "operations", "management", "underwriter"))],
)


@router.get("/providers", response_model=list[ProviderOut])
async def list_providers(db: AsyncSession = Depends(get_db)):
    return (await db.scalars(select(InsuranceProvider))).all()


@router.post("/providers", response_model=ProviderOut, status_code=status.HTTP_201_CREATED)
async def create_provider(payload: ProviderCreate, db: AsyncSession = Depends(get_db)):
    provider = InsuranceProvider(id=uuid.uuid4(), **payload.model_dump())
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    return provider


@router.patch("/providers/{provider_id}", response_model=ProviderOut)
async def update_provider(provider_id: str, payload: ProviderUpdate, db: AsyncSession = Depends(get_db)):
    provider = await db.get(InsuranceProvider, provider_id)
    if not provider:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Provider not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(provider, field, value)

    await db.commit()
    await db.refresh(provider)
    return provider


@router.delete("/providers/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(provider_id: str, db: AsyncSession = Depends(get_db)):
    """Permanently removes a provider and its own configuration (rate-card
    vehicle classes/tiers/extensions/free benefits, products, product
    plans). Refuses when the provider has any quote or policy history -
    that's real customer and financial data, and no amount of "the admin
    asked for it" makes deleting it safe; deactivating (PATCH status to
    inactive) is the right way to retire a provider that has ever quoted
    or issued anything real. A provider that was only ever set up and
    never used can be removed outright.
    """
    provider = await db.get(InsuranceProvider, provider_id)
    if not provider:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Provider not found")

    quote_count = await db.scalar(select(func.count()).select_from(Quote).where(Quote.provider_id == provider_id))
    policy_count = await db.scalar(select(func.count()).select_from(Policy).where(Policy.provider_id == provider_id))
    if quote_count or policy_count:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"This provider has {quote_count} quote(s) and {policy_count} policy record(s) - deleting it would "
            "destroy that history. Deactivate it instead (set status to inactive) to stop it quoting without "
            "losing records.",
        )

    product_ids = (
        await db.scalars(select(InsuranceProduct.id).where(InsuranceProduct.provider_id == provider_id))
    ).all()
    if product_ids:
        await db.execute(delete(InsuranceProductPlan).where(InsuranceProductPlan.product_id.in_(product_ids)))
        await db.execute(delete(InsuranceProduct).where(InsuranceProduct.provider_id == provider_id))

    class_ids = (
        await db.scalars(select(RateCardVehicleClass.id).where(RateCardVehicleClass.provider_id == provider_id))
    ).all()
    if class_ids:
        await db.execute(delete(RateCardTier).where(RateCardTier.vehicle_class_id.in_(class_ids)))
        await db.execute(delete(RateCardExcess).where(RateCardExcess.vehicle_class_id.in_(class_ids)))
        await db.execute(delete(RateCardVehicleClass).where(RateCardVehicleClass.provider_id == provider_id))
    await db.execute(delete(RateCardExtension).where(RateCardExtension.provider_id == provider_id))
    await db.execute(delete(RateCardFreeBenefit).where(RateCardFreeBenefit.provider_id == provider_id))

    await db.delete(provider)
    await db.commit()\


@router.delete("/providers/{provider_id}/force")
async def force_delete_provider_route(
    provider_id: str,
    confirm: str,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(get_current_claims),
):
    """Destroys this provider AND every quote, application, policy,
    payment, claim, sticker, renewal and financing record that depends on
    it - whatever history exists. Nothing this deletes can be recovered.

    Only super_admin may call this (checked below, on top of this
    router's normal role gate) - underwriter/operations/management can
    use the ordinary DELETE above, which refuses when history exists.

    `confirm` must exactly equal the provider's current name - a
    deliberate extra step, the same "type the name to confirm" pattern
    used for destroying a GitHub repo, so this can't be triggered by a
    single misclick or a script that assumed the safe endpoint.
    """
    if claims.get("role") != "super_admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a super_admin can force-delete a provider")

    provider = await db.get(InsuranceProvider, provider_id)
    if not provider:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Provider not found")
    if confirm != provider.name:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Confirmation text must exactly match the provider's name ('{provider.name}') to proceed.",
        )

    counts = await force_delete_provider(db, provider_id)
    return {
        "deleted_provider": provider.name,
        "deleted": {
            "payments": counts.payments,
            "policies": counts.policies,
            "applications": counts.applications,
            "quotes": counts.quotes,
            "claims": counts.claims,
            "stickers": counts.stickers,
            "renewals": counts.renewals,
            "financing_applications": counts.financing_applications,
            "financing_agreements": counts.financing_agreements,
            "referrals_unlinked": counts.referrals_unlinked,
            "products": counts.products,
            "vehicle_classes": counts.vehicle_classes,
            "extensions": counts.extensions,
            "free_benefits": counts.free_benefits,
        },
    }


@router.get("/products", response_model=list[ProductOut])
async def list_products(db: AsyncSession = Depends(get_db)):
    return (await db.scalars(select(InsuranceProduct))).all()


@router.post("/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(payload: ProductCreate, db: AsyncSession = Depends(get_db)):
    product = InsuranceProduct(id=uuid.uuid4(), **payload.model_dump())
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


@router.get("/applications", response_model=list[ApplicationOut])
async def list_applications(db: AsyncSession = Depends(get_db), status_filter: str | None = None):
    stmt = select(Application).order_by(Application.created_at.desc())
    if status_filter:
        stmt = stmt.where(Application.status == status_filter)
    return (await db.scalars(stmt)).all()


@router.post("/applications/{application_id}/approve", response_model=ApplicationOut)
async def approve(application_id: str, db: AsyncSession = Depends(get_db)):
    return await approve_application(db, application_id)


@router.get("/applications/{application_id}", response_model=ApplicationDetailOut)
async def get_application(application_id: str, db: AsyncSession = Depends(get_db)):
    """Full detail view - applicant details, customer, quote/coverage,
    vehicle/asset, documents, and decision history - so an underwriter has
    everything needed to decide the application in one place."""
    return await get_application_detail(db, application_id)


@router.post("/applications/{application_id}/transition", response_model=ApplicationOut)
async def transition(
    application_id: str,
    payload: ApplicationTransitionRequest,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(get_current_claims),
):
    """Decide a submitted application: move it to 'approved' (next stage)
    or 'rejected' (declined), with an optional note recorded against it.
    Also handles correcting a mistaken decision (approved -> rejected or
    rejected -> approved), which requires a non-empty note as a reason -
    service layer returns 400 if one isn't given. Does not replace the
    existing /approve route above."""
    return await transition_application(db, application_id, payload.to_status, claims.get("sub"), payload.notes)


@router.get("/applications/{application_id}/documents/{document_id}/url")
async def get_application_document_link(application_id: str, document_id: str, db: AsyncSession = Depends(get_db)):
    """A short-lived signed URL so staff can open an uploaded document."""
    url = await get_application_document_url(db, application_id, document_id)
    return {"url": url}