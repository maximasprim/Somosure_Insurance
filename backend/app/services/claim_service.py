import random
import string
from datetime import date

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import ALLOWED_CONTENT_TYPES, MAX_UPLOAD_BYTES, get_storage
from app.models.claim import CLAIM_STATUSES, Claim, ClaimDocument, ClaimEvent
from app.models.policy import Policy
from app.models.provider import InsuranceProvider
from app.providers.registry import get_adapter

# Only forward transitions a staff member can make directly are allowed
# here - "settled"/"closed" require going through "approved" first,
# mirroring the sticker workflow's fraud-prevention pattern (no skipping
# steps). Automated/system-driven transitions (submitted -> under_review)
# happen inside submit_claim / provider sync, not through this map.
ALLOWED_STAFF_TRANSITIONS = {
    "reported": {"documents_required", "submitted"},
    "documents_required": {"submitted"},
    "submitted": {"under_review"},
    "under_review": {"insurer_review", "approved", "rejected"},
    "insurer_review": {"approved", "rejected"},
    "approved": {"settled"},
    "settled": {"closed"},
    "rejected": {"closed"},
}


def generate_claim_reference() -> str:
    year = date.today().year
    suffix = "".join(random.choices(string.digits, k=6))
    return f"SOM-CLM-{year}-{suffix}"


async def report_claim(
    db: AsyncSession, policy_id: str, customer_id: str, incident_date, incident_description: str, incident_location: str | None
) -> Claim:
    policy = await db.get(Policy, policy_id)
    if not policy:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Policy not found")
    if str(policy.customer_id) != customer_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This policy does not belong to this customer")
    if policy.status not in ("active", "expired"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Claims can only be reported against an active or recently expired policy")

    claim = Claim(
        reference=generate_claim_reference(),
        policy_id=policy_id,
        customer_id=customer_id,
        incident_date=incident_date,
        incident_description=incident_description,
        incident_location=incident_location,
        status="reported",
    )
    db.add(claim)
    await db.flush()
    db.add(ClaimEvent(claim_id=claim.id, event_type="status_changed", from_status=None, to_status="reported"))

    await db.commit()
    await db.refresh(claim)
    return claim


async def upload_claim_document(db: AsyncSession, claim_id: str, document_type: str, file: UploadFile) -> ClaimDocument:
    claim = await db.get(Claim, claim_id)
    if not claim:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Claim not found")

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Only PDF, JPEG, or PNG documents are accepted")

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File exceeds the 10MB limit")

    storage = get_storage()
    storage_path = await storage.save(f"claims/{claim_id}", file.filename or "document", content)

    doc = ClaimDocument(
        claim_id=claim.id, document_type=document_type, storage_path=storage_path,
        original_filename=file.filename or "document", content_type=file.content_type, size_bytes=len(content),
    )
    db.add(doc)

    if claim.status == "reported":
        claim.status = "documents_required"

    db.add(ClaimEvent(claim_id=claim.id, event_type="document_uploaded", notes=f"Uploaded {document_type}"))
    await db.commit()
    await db.refresh(doc)
    return doc


async def submit_claim(db: AsyncSession, claim_id: str) -> Claim:
    claim = await db.get(Claim, claim_id)
    if not claim:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Claim not found")

    docs = (await db.scalars(select(ClaimDocument).where(ClaimDocument.claim_id == claim.id))).all()
    if not docs:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "At least one supporting document is required before submitting")

    policy = await db.get(Policy, claim.policy_id)
    provider = await db.get(InsuranceProvider, policy.provider_id)
    adapter = get_adapter(provider)

    try:
        # Real adapters that implement submit_claim will genuinely submit
        # to the insurer here; MockProvider and every pending real adapter
        # either simulate or raise NotImplementedError, in which case
        # staff-assisted processing (spec §15) takes over below.
        result = await adapter.submit_claim(policy.policy_number, {"description": claim.incident_description})
        claim.provider_reference = result.claim_reference
        claim.status = "under_review"
    except NotImplementedError:
        # Staff-assisted path - no provider claims API available.
        claim.status = "submitted"

    db.add(ClaimEvent(claim_id=claim.id, event_type="status_changed", from_status="documents_required", to_status=claim.status))
    await db.commit()
    await db.refresh(claim)
    return claim


async def transition_claim(db: AsyncSession, claim_id: str, to_status: str, actor_user_id: str | None, notes: str | None) -> Claim:
    claim = await db.get(Claim, claim_id)
    if not claim:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Claim not found")

    allowed = ALLOWED_STAFF_TRANSITIONS.get(claim.status, set())
    if to_status not in allowed:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Cannot move claim from '{claim.status}' to '{to_status}' - allowed next steps: {sorted(allowed) or 'none'}",
        )

    db.add(ClaimEvent(claim_id=claim.id, event_type="status_changed", from_status=claim.status, to_status=to_status, actor_user_id=actor_user_id, notes=notes))
    claim.status = to_status

    await db.commit()
    await db.refresh(claim)
    return claim
