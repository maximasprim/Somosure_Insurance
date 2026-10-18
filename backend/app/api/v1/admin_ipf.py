"""Admin endpoints for the Bidii Credit IPF extras: early settlement, post-dated
cheques, linked/unlinked + tracker, the original logbook, and loan officers with
their commission. Same roles as the rest of the financing admin."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.context import record_event
from app.core.database import get_db
from app.core.security import get_current_claims, require_roles
from app.schemas.ipf import (
    AssignOfficerRequest,
    ChequeCreate,
    ChequeOut,
    ChequeUpdate,
    CommissionBasisRequest,
    CommissionTransitionRequest,
    IpfDetailOut,
    IpfTypeRequest,
    LoanOfficerCreate,
    LoanOfficerOut,
    LoanOfficerSummaryOut,
    LoanOfficerUpdate,
    LogbookRequest,
    OfficerCommissionOut,
    SettleRequest,
    SettlementOut,
    SettlementQuoteOut,
    TrackerRequest,
)
from app.services import ipf_service

ROLES = ("super_admin", "finance_officer", "management")

router = APIRouter(
    prefix="/api/v1/admin/financing",
    tags=["financing-ipf"],
    dependencies=[Depends(require_roles(*ROLES))],
)

officers_router = APIRouter(
    prefix="/api/v1/admin/loan-officers",
    tags=["loan-officers"],
    dependencies=[Depends(require_roles(*ROLES))],
)


# --- per financing application ----------------------------------------------------------------


@router.get("/applications/{application_id}/ipf", response_model=IpfDetailOut)
async def get_ipf(application_id: str, db: AsyncSession = Depends(get_db)):
    """Everything IPF-specific about one request in one call: type, loan officer,
    tracker, original logbook, cheques, and any early-settlement quote or record."""
    return await ipf_service.get_ipf_detail(db, application_id)


@router.post("/applications/{application_id}/ipf-type", response_model=IpfDetailOut)
async def set_type(
    application_id: str,
    payload: IpfTypeRequest,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(get_current_claims),
):
    await ipf_service.set_ipf_type(db, application_id, payload.ipf_type, claims.get("sub"))
    return await ipf_service.get_ipf_detail(db, application_id)


@router.post("/applications/{application_id}/loan-officer", response_model=IpfDetailOut)
async def assign_officer(
    application_id: str,
    payload: AssignOfficerRequest,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(get_current_claims),
):
    await ipf_service.assign_loan_officer(db, application_id, payload.loan_officer_id, claims.get("sub"))
    return await ipf_service.get_ipf_detail(db, application_id)


@router.post("/applications/{application_id}/tracker", response_model=IpfDetailOut)
async def set_tracker(
    application_id: str,
    payload: TrackerRequest,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(get_current_claims),
):
    await ipf_service.record_tracker(db, application_id, payload.installed, payload.provider, payload.device_id, claims.get("sub"))
    return await ipf_service.get_ipf_detail(db, application_id)


@router.post("/applications/{application_id}/original-logbook", response_model=IpfDetailOut)
async def set_original_logbook(
    application_id: str,
    payload: LogbookRequest,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(get_current_claims),
):
    await ipf_service.record_original_logbook(db, application_id, payload.received, claims.get("sub"))
    return await ipf_service.get_ipf_detail(db, application_id)


@router.post("/applications/{application_id}/cheques", response_model=ChequeOut)
async def add_cheque(
    application_id: str,
    payload: ChequeCreate,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(get_current_claims),
):
    return await ipf_service.add_cheque(db, application_id, payload, claims.get("sub"))


@router.patch("/applications/{application_id}/cheques/{cheque_id}", response_model=ChequeOut)
async def update_cheque(
    application_id: str,
    cheque_id: str,
    payload: ChequeUpdate,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(get_current_claims),
):
    return await ipf_service.update_cheque(db, application_id, cheque_id, payload, claims.get("sub"))


@router.delete("/applications/{application_id}/cheques/{cheque_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cheque(
    application_id: str,
    cheque_id: str,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(get_current_claims),
):
    await ipf_service.delete_cheque(db, application_id, cheque_id, claims.get("sub"))


@router.get("/applications/{application_id}/early-settlement", response_model=SettlementQuoteOut)
async def early_settlement_quote(application_id: str, db: AsyncSession = Depends(get_db)):
    """What it would cost the client to clear the loan right now. Read-only."""
    return await ipf_service.early_settlement_quote(db, application_id)


@router.post("/applications/{application_id}/early-settlement", response_model=SettlementOut)
async def settle_early(
    application_id: str,
    payload: SettleRequest,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(get_current_claims),
):
    """Record that the client has paid to clear the loan early. Waives the remaining
    instalments and closes the agreement."""
    settlement = await ipf_service.settle_early(db, application_id, claims.get("sub"), payload.payment_reference, payload.notes)
    record_event(
        "financing.early_settlement",
        entity_type="financing_applications",
        entity_id=application_id,
        summary=f"Loan settled early for KES {settlement.total_paid:,}",
        payment_reference=payload.payment_reference,
    )
    return settlement


# --- loan officers ---------------------------------------------------------------------------------


@officers_router.get("", response_model=list[LoanOfficerSummaryOut])
async def list_officers(db: AsyncSession = Depends(get_db)):
    return await ipf_service.officers_with_results(db)


@officers_router.post("", response_model=LoanOfficerOut, status_code=status.HTTP_201_CREATED)
async def create_officer(payload: LoanOfficerCreate, db: AsyncSession = Depends(get_db)):
    return await ipf_service.create_officer(db, payload)


@officers_router.get("/commissions", response_model=list[OfficerCommissionOut])
async def list_commissions(
    officer_id: str | None = None, status_filter: str | None = None, db: AsyncSession = Depends(get_db)
):
    return await ipf_service.list_commissions(db, officer_id=officer_id, status_filter=status_filter)


@officers_router.post("/commissions/{commission_id}/basis", response_model=OfficerCommissionOut)
async def set_commission_basis(commission_id: str, payload: CommissionBasisRequest, db: AsyncSession = Depends(get_db)):
    """Enter Somosure's net commission on the policy; the officer's share is worked out from it."""
    await ipf_service.set_commission_basis(db, commission_id, payload.net_commission)
    return await ipf_service.commission_view(db, commission_id)


@officers_router.post("/commissions/{commission_id}/transition", response_model=OfficerCommissionOut)
async def transition_commission(
    commission_id: str,
    payload: CommissionTransitionRequest,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(get_current_claims),
):
    row = await ipf_service.transition_commission(db, commission_id, payload.to_status, payload.payout_reference, claims.get("sub"))
    record_event(
        f"loan_officer_commission.{payload.to_status}",
        entity_type="loan_officer_commissions",
        entity_id=commission_id,
        summary=f"Loan officer commission marked {payload.to_status}" + (f" (KES {row.commission_amount:,})" if row.commission_amount else ""),
        payout_reference=payload.payout_reference,
    )
    return await ipf_service.commission_view(db, commission_id)


@officers_router.patch("/{officer_id}", response_model=LoanOfficerOut)
async def update_officer(officer_id: str, payload: LoanOfficerUpdate, db: AsyncSession = Depends(get_db)):
    return await ipf_service.update_officer(db, officer_id, payload)
