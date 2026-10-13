from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_optional_customer_id
from app.core.guest_access import GUEST_HEADER, issue_token
from app.core.ownership import customer_for_quote, load_application
from app.models.application import Application
from app.schemas.application import ApplicationCreate, ApplicationDocumentOut, ApplicationOut
from app.schemas.affiliate import ApplicationDiscountOut
from app.schemas.documents import ApplicationStatusOut, DocumentChecklistOut
from app.services.application_service import create_application, submit_application, upload_document
from app.services.document_reuse_service import application_checklist

router = APIRouter(prefix="/api/v1/applications", tags=["applications"])


@router.post("", response_model=ApplicationOut)
async def create(
    payload: ApplicationCreate,
    response: Response,
    db: AsyncSession = Depends(get_db),
    authed_customer_id: str | None = Depends(get_optional_customer_id),
):
    # The customer must be the one the server resolved for this quote (or the
    # logged-in customer) - the id the browser sends is not trusted on its own.
    customer_id = await customer_for_quote(db, authed_customer_id, payload.quote_id, payload.customer_id)
    application = await create_application(
        db,
        quote_id=payload.quote_id,
        customer_id=customer_id,
        applicant_details=payload.applicant_details,
        vehicle_id=payload.vehicle_id,
        insured_asset_id=payload.insured_asset_id,
    )
    # Proof of ownership for a guest: a signed token for THIS application only.
    # The frontend keeps it and sends it back on every later call.
    response.headers[GUEST_HEADER] = issue_token("application", application.id)
    return application


@router.post("/{application_id}/documents", response_model=ApplicationDocumentOut)
async def upload(
    application_id: str,
    request: Request,
    document_type: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    authed_customer_id: str | None = Depends(get_optional_customer_id),
):
    await load_application(db, request, authed_customer_id, application_id)
    return await upload_document(db, application_id, document_type, file)


@router.post("/{application_id}/submit", response_model=ApplicationOut)
async def submit(
    application_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    authed_customer_id: str | None = Depends(get_optional_customer_id),
):
    await load_application(db, request, authed_customer_id, application_id)
    return await submit_application(db, application_id)


@router.get("/{application_id}/status", response_model=ApplicationStatusOut)
async def get_status(
    application_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    authed_customer_id: str | None = Depends(get_optional_customer_id),
):
    """Status only (never staff notes) - lets the "under review" screen
    notice approval or rejection by itself instead of asking the customer
    to click a button and hope. Only the owner (logged in, or holding the
    guest token issued when the application was created) can read it."""
    return await load_application(db, request, authed_customer_id, application_id)


@router.get("/{application_id}/documents/checklist", response_model=DocumentChecklistOut)
async def documents_checklist(
    application_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    authed_customer_id: str | None = Depends(get_optional_customer_id),
):
    await load_application(db, request, authed_customer_id, application_id)
    return await application_checklist(db, application_id, attach=False)


@router.post("/{application_id}/documents/prepare", response_model=DocumentChecklistOut)
async def prepare_documents(
    application_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    authed_customer_id: str | None = Depends(get_optional_customer_id),
):
    """Attaches identity documents (national ID, KRA PIN) the logged-in
    customer already uploaded on an earlier application, then returns what
    is still needed. A guest simply gets the checklist - nothing is reused
    for someone who isn't logged in. Safe to call repeatedly."""
    await load_application(db, request, authed_customer_id, application_id)
    return await application_checklist(db, application_id, attach=True, authed_customer_id=authed_customer_id)


@router.get("/{application_id}/discount", response_model=ApplicationDiscountOut)
async def get_discount(
    application_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    authed_customer_id: str | None = Depends(get_optional_customer_id),
):
    """The referral discount staff applied to this application, if any - so the
    payment screen can show the amount that will actually be charged. Same access
    rule as the status endpoint."""
    from app.services.referral_discount_service import application_discount

    await load_application(db, request, authed_customer_id, application_id)
    return await application_discount(db, application_id)

