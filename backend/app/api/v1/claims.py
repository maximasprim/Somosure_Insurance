from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_customer
from app.models.claim import Claim
from app.models.customer import Customer
from app.schemas.claim import ClaimDocumentOut, ClaimOut, ClaimReportRequest
from app.services.claim_service import report_claim, submit_claim, upload_claim_document

# Claims are for signed-in customers: every call is tied to the logged-in
# customer's own record, and a claim can only be read or changed by the customer
# who reported it. (Previously these endpoints were open and trusted the
# customer_id / claim id sent by the browser.)
router = APIRouter(prefix="/api/v1/claims", tags=["claims"])


async def _own_claim(db: AsyncSession, customer: Customer, claim_id: str) -> Claim:
    import uuid

    try:
        key = uuid.UUID(str(claim_id))
    except ValueError:
        key = None
    claim = await db.get(Claim, key) if key else None
    if not claim or str(claim.customer_id) != str(customer.id):
        # Same answer for "doesn't exist" and "isn't yours", so ids can't be probed.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Claim not found")
    return claim


@router.post("", response_model=ClaimOut)
async def report(
    payload: ClaimReportRequest,
    db: AsyncSession = Depends(get_db),
    customer: Customer = Depends(get_current_customer),
):
    if payload.customer_id and str(payload.customer_id) != str(customer.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This policy does not belong to this customer")
    return await report_claim(
        db, payload.policy_id, str(customer.id), payload.incident_date, payload.incident_description, payload.incident_location
    )


@router.post("/{claim_id}/documents", response_model=ClaimDocumentOut)
async def upload(
    claim_id: str,
    document_type: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    customer: Customer = Depends(get_current_customer),
):
    await _own_claim(db, customer, claim_id)
    return await upload_claim_document(db, claim_id, document_type, file)


@router.post("/{claim_id}/submit", response_model=ClaimOut)
async def submit(claim_id: str, db: AsyncSession = Depends(get_db), customer: Customer = Depends(get_current_customer)):
    await _own_claim(db, customer, claim_id)
    return await submit_claim(db, claim_id)


@router.get("/{claim_id}", response_model=ClaimOut)
async def get_claim(claim_id: str, db: AsyncSession = Depends(get_db), customer: Customer = Depends(get_current_customer)):
    return await _own_claim(db, customer, claim_id)
