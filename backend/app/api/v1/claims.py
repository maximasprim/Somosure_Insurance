from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.claim import ClaimDocumentOut, ClaimOut, ClaimReportRequest
from app.services.claim_service import report_claim, submit_claim, upload_claim_document

router = APIRouter(prefix="/api/v1/claims", tags=["claims"])


@router.post("", response_model=ClaimOut)
async def report(payload: ClaimReportRequest, db: AsyncSession = Depends(get_db)):
    return await report_claim(
        db, payload.policy_id, payload.customer_id, payload.incident_date, payload.incident_description, payload.incident_location
    )


@router.post("/{claim_id}/documents", response_model=ClaimDocumentOut)
async def upload(claim_id: str, document_type: str, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    return await upload_claim_document(db, claim_id, document_type, file)


@router.post("/{claim_id}/submit", response_model=ClaimOut)
async def submit(claim_id: str, db: AsyncSession = Depends(get_db)):
    return await submit_claim(db, claim_id)


@router.get("/{claim_id}", response_model=ClaimOut)
async def get_claim(claim_id: str, db: AsyncSession = Depends(get_db)):
    from fastapi import HTTPException, status

    from app.models.claim import Claim

    claim = await db.get(Claim, claim_id)
    if not claim:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Claim not found")
    return claim
