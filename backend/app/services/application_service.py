import random
import string
import uuid
from datetime import date

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import ALLOWED_CONTENT_TYPES, MAX_UPLOAD_BYTES, get_storage
from app.models.application import Application, ApplicationDocument, ApplicationEvent
from app.models.asset import InsuredAsset, Vehicle
from app.models.customer import Customer
from app.models.provider import InsuranceProduct, InsuranceProvider
from app.models.quote import Quote
from app.schemas.application import (
    ApplicationCustomerOut,
    ApplicationDetailOut,
    ApplicationInsuredAssetOut,
    ApplicationQuoteOut,
    ApplicationVehicleOut,
)

# Only forward transitions a staff member can make directly, mirroring
# ALLOWED_STAFF_TRANSITIONS in claim_service.py. Kept to exactly what
# approve_application already enforced (submitted -> approved) plus the
# sibling "decline" path, since nothing in this codebase today puts an
# application into "under_review" or "payment_pending" for staff to act on.
ALLOWED_STAFF_TRANSITIONS: dict[str, set[str]] = {
    "submitted": {"approved", "rejected"},
}


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


async def transition_application(
    db: AsyncSession, application_id: str, to_status: str, actor_user_id: str | None, notes: str | None
) -> Application:
    """The general decision endpoint behind the admin review screen: move a
    submitted application to "approved" (next stage) or "rejected"
    (declined), with an optional note, recorded permanently on
    ApplicationEvent. Same shape as claim_service.transition_claim.

    This does not replace approve_application above - that function (and
    the /approve route + tests that call it) is left exactly as it was.
    """
    application = await db.get(Application, application_id)
    if not application:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")

    allowed = ALLOWED_STAFF_TRANSITIONS.get(application.status, set())
    if to_status not in allowed:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Cannot move application from '{application.status}' to '{to_status}' - allowed next steps: {sorted(allowed) or 'none'}",
        )

    db.add(
        ApplicationEvent(
            application_id=application.id,
            event_type="status_changed",
            from_status=application.status,
            to_status=to_status,
            actor_user_id=actor_user_id,
            notes=notes,
        )
    )
    application.status = to_status

    await db.commit()
    await db.refresh(application)
    return application


async def get_application_detail(db: AsyncSession, application_id: str) -> ApplicationDetailOut:
    """Everything an underwriter needs on one screen to decide an
    application: applicant details, the customer, the quote they picked
    (with provider/product names resolved), the vehicle or insured asset,
    every uploaded document, and the full decision/notes history."""
    application = await db.get(Application, application_id)
    if not application:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")

    customer = await db.get(Customer, application.customer_id)
    if not customer:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer on this application no longer exists")

    quote = await db.get(Quote, application.quote_id)
    if not quote:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Quote on this application no longer exists")
    provider = await db.get(InsuranceProvider, quote.provider_id)
    product = await db.get(InsuranceProduct, quote.product_id) if quote.product_id else None

    vehicle = await db.get(Vehicle, application.vehicle_id) if application.vehicle_id else None
    insured_asset = await db.get(InsuredAsset, application.insured_asset_id) if application.insured_asset_id else None

    documents = (
        await db.scalars(
            select(ApplicationDocument)
            .where(ApplicationDocument.application_id == application.id)
            .order_by(ApplicationDocument.uploaded_at.asc())
        )
    ).all()
    events = (
        await db.scalars(
            select(ApplicationEvent)
            .where(ApplicationEvent.application_id == application.id)
            .order_by(ApplicationEvent.created_at.desc())
        )
    ).all()

    return ApplicationDetailOut(
        id=application.id,
        reference=application.reference,
        status=application.status,
        applicant_details=application.applicant_details,
        provider_reference=application.provider_reference,
        created_at=application.created_at,
        updated_at=application.updated_at,
        customer=ApplicationCustomerOut.model_validate(customer),
        quote=ApplicationQuoteOut(
            id=quote.id,
            provider_name=provider.name if provider else "Unknown provider",
            underlying_provider_name=quote.underlying_provider_name,
            product_name=product.name if product else None,
            premium=quote.premium,
            taxes=quote.taxes,
            fees=quote.fees,
            total=quote.total,
            currency=quote.currency,
            coverage=quote.coverage,
            exclusions=quote.exclusions,
            deductibles=quote.deductibles,
            is_mock=quote.is_mock,
        ),
        vehicle=ApplicationVehicleOut.model_validate(vehicle) if vehicle else None,
        insured_asset=ApplicationInsuredAssetOut.model_validate(insured_asset) if insured_asset else None,
        documents=documents,
        events=events,
    )


async def get_application_document_url(db: AsyncSession, application_id: str, document_id: str) -> str:
    """A short-lived signed URL so staff can actually open/view an uploaded
    document (national ID, logbook, inspection report, ...) while deciding
    an application - reuses the same storage abstraction document uploads
    already go through; never returns a public/permanent link."""
    document = await db.get(ApplicationDocument, document_id)
    if not document or str(document.application_id) != str(application_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found on this application")

    storage = get_storage()
    return await storage.get_signed_url(document.storage_path)