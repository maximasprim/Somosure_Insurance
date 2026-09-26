import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import  get_current_claims, require_roles
from app.models.application import Application
from app.models.provider import InsuranceProduct, InsuranceProvider
from app.schemas.admin import ProductCreate, ProductOut, ProviderCreate, ProviderOut, ProviderUpdate
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
    Does not replace the existing /approve route above."""
    return await transition_application(db, application_id, payload.to_status, claims.get("sub"), payload.notes)
 
 
@router.get("/applications/{application_id}/documents/{document_id}/url")
async def get_application_document_link(application_id: str, document_id: str, db: AsyncSession = Depends(get_db)):
    """A short-lived signed URL so staff can open an uploaded document."""
    url = await get_application_document_url(db, application_id, document_id)
    return {"url": url}
 