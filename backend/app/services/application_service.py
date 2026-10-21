import asyncio
import logging
import random
import string
import uuid
from datetime import date

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import ALLOWED_CONTENT_TYPES, MAX_UPLOAD_BYTES, get_storage
from app.services.document_intake import screen_upload
from app.models.application import Application, ApplicationDocument, ApplicationEvent
from app.models.asset import InsuredAsset, Vehicle
from app.models.customer import Customer
from app.models.financing import FinancingApplication
from app.models.policy import Policy
from app.models.provider import InsuranceProduct, InsuranceProvider
from app.models.quote import Quote, QuoteRequest
from app.schemas.application import (
    ApplicationCustomerOut,
    ApplicationDetailOut,
    ApplicationFinancingOut,
    ApplicationInsuredAssetOut,
    ApplicationQuoteOut,
    ApplicationRescanOut,
    ApplicationVehicleOut,
)
from app.services.applicant_details import (
    apply_extracted,
    effective_applicant_details,
    fill_customer_blanks,
    seed_applicant_details,
)
from app.services.document_extraction import READABLE_FIELDS, extract_from_document

logger = logging.getLogger("somosure.application_service")

# Forward decisions plus corrections. "submitted" -> approved/rejected is
# the first underwriting decision (notes optional, as before). The reverse
# pairs let staff correct a mistaken approve/reject - see OVERRIDE_TRANSITIONS
# below, which requires a reason for exactly those reversal moves.
ALLOWED_STAFF_TRANSITIONS: dict[str, set[str]] = {
    "submitted": {"approved", "rejected"},
    "approved": {"rejected"},
    "rejected": {"approved"},
}

# A transition that reverses a decision already made, rather than making
# the first one - these require a non-empty reason (enforced in
# transition_application below) so there's always an audit trail for why a
# mistaken approve/reject was corrected.
OVERRIDE_TRANSITIONS: set[tuple[str, str]] = {("approved", "rejected"), ("rejected", "approved")}


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

    # Copy what the customer filled in on the quote form onto the application,
    # so the underwriter sees it. (The browser sends an empty dict; anything it
    # does send still wins over the copied answers.)
    quote_request = await db.get(QuoteRequest, quote.quote_request_id)
    applicant_details = seed_applicant_details(applicant_details, quote_request.input_data if quote_request else None)

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

    # Screen the file before it is stored (see document_intake.py) - raises
    # a 422 with a customer-friendly reason in strict mode.
    existing_docs = (
        await db.scalars(select(ApplicationDocument).where(ApplicationDocument.application_id == application.id))
    ).all()
    outcome = await screen_upload(document_type, file.filename or "document", content, existing_docs)

    storage = get_storage()
    storage_path = await storage.save(f"applications/{application_id}", file.filename or "document", content)

    doc = ApplicationDocument(
        application_id=application.id,
        document_type=document_type,
        storage_path=storage_path,
        original_filename=file.filename or "document",
        content_type=file.content_type,
        size_bytes=len(content),
        status=outcome.status,
        validation_notes=outcome.notes,
        file_hash=outcome.file_hash,
    )
    db.add(doc)

    # Append anything read off the document (KRA PIN, national ID number...) to
    # the applicant details and fill the customer's blanks. Must never stop an
    # upload, so any problem here is logged and ignored.
    if outcome.extracted:
        try:
            await _record_extracted_details(db, application, outcome.extracted, document_type)
        except Exception:
            logger.warning("Could not record details read from a %s document", document_type, exc_info=True)

    if application.status == "draft":
        application.status = "documents_required"

    await db.commit()
    await db.refresh(doc)
    return doc


async def _record_extracted_details(
    db: AsyncSession, application: Application, fields: dict[str, str], document_type: str
) -> None:
    application.applicant_details = apply_extracted(application.applicant_details, fields, document_type)
    customer = await db.get(Customer, application.customer_id)
    if customer:
        fill_customer_blanks(customer, fields)


async def rescan_application_documents(db: AsyncSession, application_id: str) -> ApplicationRescanOut:
    """Re-reads ID number / KRA PIN / logbook numbers / valuation details from the documents already
    uploaded on this application - for applications that were submitted before
    automatic reading existed, or where a clearer copy has since been uploaded.
    Oldest first, so the newest upload wins. Never removes anything."""
    application = await db.get(Application, application_id)
    if not application:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")

    docs = (
        await db.scalars(
            select(ApplicationDocument)
            .where(
                ApplicationDocument.application_id == application.id,
                ApplicationDocument.document_type.in_(list(READABLE_FIELDS)),
            )
            .order_by(ApplicationDocument.uploaded_at.asc())
        )
    ).all()
    if not docs:
        return ApplicationRescanOut(
            documents_read=0, fields_found=[], message="No ID, KRA PIN, logbook or valuation documents have been uploaded yet."
        )

    storage = get_storage()
    read = 0
    found: dict[str, str] = {}
    for doc in docs:
        try:
            content = await storage.read(doc.storage_path)
        except Exception:
            logger.warning("Could not read stored document %s back for re-scan", doc.id, exc_info=True)
            continue
        read += 1
        fields = await asyncio.to_thread(extract_from_document, doc.document_type, content)
        if fields:
            application.applicant_details = apply_extracted(application.applicant_details, fields, doc.document_type)
            found.update(fields)

    if found:
        customer = await db.get(Customer, application.customer_id)
        if customer:
            fill_customer_blanks(customer, found)
        await db.commit()
        message = f"Read {len(found)} detail(s) from {read} document(s)."
    elif read == 0:
        message = "The uploaded files could not be opened for re-reading."
    else:
        message = "No ID number, KRA PIN, logbook or valuation details could be read - the copies may be too blurry or image-only."
    return ApplicationRescanOut(documents_read=read, fields_found=sorted(found), message=message)


def _resolve_product_name(product: InsuranceProduct | None, quote: Quote, category: str | None) -> str | None:
    """What to show as the quote's "product". Rate-card and mock quotes are not
    tied to a catalogue product row, so fall back to the cover summary the
    provider returned (e.g. "Private car - COMPREHENSIVE cover"), then to the
    category."""
    if product and product.name:
        return product.name
    summary = (quote.coverage or {}).get("summary")
    if isinstance(summary, str) and summary.strip():
        return summary.strip()
    if category:
        return f"{category.replace('_', ' ').title()} insurance"
    return None


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

    Also handles correcting a mistaken decision (approved -> rejected or
    rejected -> approved) - see OVERRIDE_TRANSITIONS, which requires a
    reason for exactly those reversal moves so there's always a record of
    why an existing decision was changed.

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

    is_override = (application.status, to_status) in OVERRIDE_TRANSITIONS
    if is_override and not (notes and notes.strip()):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A reason is required to change an existing approve/reject decision")

    if is_override and application.status == "approved" and to_status == "rejected":
        # A policy may already have been issued off this approval (see
        # issue_policy in policy_service.py) - rejecting the application
        # after the fact would leave a live policy pointing at a now-
        # rejected application, so that has to be handled deliberately
        # (e.g. cancelling the policy itself) rather than silently here.
        existing_policy = await db.scalar(select(Policy).where(Policy.application_id == application.id))
        if existing_policy:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Policy {existing_policy.policy_number} has already been issued for this application - "
                "cancel or handle the policy first before rejecting the application it came from",
            )

    db.add(
        ApplicationEvent(
            application_id=application.id,
            event_type="status_override" if is_override else "status_changed",
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
    quote_request = await db.get(QuoteRequest, quote.quote_request_id)
    category = quote_request.category if quote_request else None

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

    # The customer's financing request for this same quote, if any - shown beside the
    # insurance status because the two are approved separately.
    financing = await db.scalar(
        select(FinancingApplication)
        .where(
            FinancingApplication.quote_id == application.quote_id,
            FinancingApplication.customer_id == application.customer_id,
        )
        .order_by(FinancingApplication.created_at.desc())
        .limit(1)
    )

    return ApplicationDetailOut(
        id=application.id,
        reference=application.reference,
        status=application.status,
        applicant_details=effective_applicant_details(
            application.applicant_details, quote_request.input_data if quote_request else None
        ),
        provider_reference=application.provider_reference,
        created_at=application.created_at,
        updated_at=application.updated_at,
        customer=ApplicationCustomerOut.model_validate(customer),
        quote=ApplicationQuoteOut(
            id=quote.id,
            provider_name=provider.name if provider else "Unknown provider",
            underlying_provider_name=quote.underlying_provider_name,
            product_name=_resolve_product_name(product, quote, category),
            premium=quote.premium,
            taxes=quote.taxes,
            fees=quote.fees,
            total=quote.total,
            currency=quote.currency,
            coverage=quote.coverage,
            exclusions=quote.exclusions,
            deductibles=quote.deductibles,
            is_mock=quote.is_mock,
            category=category,
            valid_until=quote.valid_until,
            request_reference=quote_request.reference if quote_request else None,
            provider_metadata=quote.provider_metadata or {},
        ),
        vehicle=ApplicationVehicleOut.model_validate(vehicle) if vehicle else None,
        insured_asset=ApplicationInsuredAssetOut.model_validate(insured_asset) if insured_asset else None,
        documents=documents,
        events=events,
        financing=ApplicationFinancingOut(id=financing.id, reference=financing.reference, status=financing.status)
        if financing
        else None,
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