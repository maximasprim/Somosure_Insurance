import random
import string
import uuid
from datetime import date

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import ALLOWED_CONTENT_TYPES, MAX_UPLOAD_BYTES, get_storage
from app.models.application import Application, ApplicationDocument
from app.models.provider import InsuranceProvider
from app.models.quote import Quote


def generate_application_reference() -> str:
    year = date.today().year
    suffix = "".join(random.choices(string.digits, k=6))
    return f"SOM-APP-{year}-{suffix}"


async def create_application(
    db: AsyncSession, quote_id: str, customer_id: str, applicant_details: dict,
    vehicle_id: str | None = None, insured_asset_id: str | None = None,
) -> Application:
    quote = await db.get(Quote, quote_id)
    if not quote:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Quote not found")
    if quote.status != "available":
        raise HTTPException(status.HTTP_409_CONFLICT, "This quote is no longer available")

    application = Application(
        reference=generate_application_reference(),
        quote_id=quote.id,
        customer_id=customer_id,
        vehicle_id=vehicle_id,
        insured_asset_id=insured_asset_id,
        applicant_details=applicant_details,
        status="draft",
    )
    db.add(application)

    quote.status = "selected"

    await db.commit()
    await db.refresh(application)
    return application


async def upload_document(
    db: AsyncSession, application_id: str, document_type: str, file: UploadFile
) -> ApplicationDocument:
    application = await db.get(Application, application_id)
    if not application:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Only PDF, JPEG, or PNG documents are accepted")

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File exceeds the 10MB limit")

    storage = get_storage()
    storage_path = await storage.save(f"applications/{application_id}", file.filename or "document", content)

    doc = ApplicationDocument(
        application_id=application.id,
        document_type=document_type,
        storage_path=storage_path,
        original_filename=file.filename or "document",
        content_type=file.content_type,
        size_bytes=len(content),
        status="uploaded",
    )
    db.add(doc)

    if application.status == "draft":
        application.status = "documents_required"

    await db.commit()
    await db.refresh(doc)
    return doc


async def submit_application(db: AsyncSession, application_id: str) -> Application:
    application = await db.get(Application, application_id)
    if not application:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")

    docs = (
        await db.scalars(select(ApplicationDocument).where(ApplicationDocument.application_id == application.id))
    ).all()
    if not docs:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "At least one document is required before submitting")

    quote = await db.get(Quote, application.quote_id)
    provider = await db.get(InsuranceProvider, quote.provider_id) if quote else None

    application.status = "submitted"
    if provider:
        # Real submission to the provider adapter happens here once the
        # provider isn't a MockProvider - kept simple for Phase 2 since
        # the adapter call itself is already proven in the quote flow.
        application.provider_reference = f"REF-{uuid.uuid4().hex[:8].upper()}"

    await db.commit()
    await db.refresh(application)
    return application


async def approve_application(db: AsyncSession, application_id: str) -> Application:
    """Underwriting sign-off - the human-in-the-loop gate (spec §47) that
    must happen before payment can be collected or a policy issued."""
    application = await db.get(Application, application_id)
    if not application:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    if application.status != "submitted":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a submitted application can be approved")

    application.status = "approved"
    await db.commit()
    await db.refresh(application)
    return application
