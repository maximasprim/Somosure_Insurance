import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_roles
from app.models.application import Application
from app.models.provider import InsuranceProduct, InsuranceProvider
from app.schemas.admin import ProductCreate, ProductOut, ProviderCreate, ProviderOut, ProviderUpdate
from app.schemas.application import ApplicationOut
from app.services.application_service import approve_application

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
