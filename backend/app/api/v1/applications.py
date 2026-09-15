from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.application import ApplicationCreate, ApplicationDocumentOut, ApplicationOut
from app.services.application_service import create_application, submit_application, upload_document

router = APIRouter(prefix="/api/v1/applications", tags=["applications"])


@router.post("", response_model=ApplicationOut)
async def create(payload: ApplicationCreate, db: AsyncSession = Depends(get_db)):
    application = await create_application(
        db,
        quote_id=payload.quote_id,
        customer_id=payload.customer_id,
        applicant_details=payload.applicant_details,
        vehicle_id=payload.vehicle_id,
        insured_asset_id=payload.insured_asset_id,
    )
    return application


@router.post("/{application_id}/documents", response_model=ApplicationDocumentOut)
async def upload(
    application_id: str,
    document_type: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    return await upload_document(db, application_id, document_type, file)


@router.post("/{application_id}/submit", response_model=ApplicationOut)
async def submit(application_id: str, db: AsyncSession = Depends(get_db)):
    return await submit_application(db, application_id)
