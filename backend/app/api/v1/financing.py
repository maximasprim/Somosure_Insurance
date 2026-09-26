from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_claims, require_roles
from app.models.financing import FinancingAgreement, FinancingApplication, FinancingInstallment
from app.schemas.financing import (
    EligibilityOut,
    EligibilityRequest,
    FinancingAgreementOut,
    FinancingApplicationCreate,
    FinancingApplicationDetailOut,
    FinancingApplicationOut,
    FinancingDocumentOut,
    FinancingSettingsOut,
    FinancingSettingsUpdate,
    FinancingTransitionRequest,
    InstallmentOut,
)
from app.services.financing_service import (
    check_eligibility,
    get_financing_application_detail,
    get_financing_document_url,
    get_financing_settings,
    submit_application,
    transition_financing_application,
    update_financing_settings,
    upload_financing_document,
)

router = APIRouter(prefix="/api/v1/financing", tags=["financing"])


@router.post("/eligibility", response_model=EligibilityOut)
async def eligibility(payload: EligibilityRequest, db: AsyncSession = Depends(get_db)):
    return await check_eligibility(
        db,
        payload.customer_id,
        payload.quote_id,
        payload.term_months,
        payload.has_existing_logbook_loan,
        payload.logbook_loan_age_months,
    )


@router.post("/applications", response_model=FinancingApplicationOut)
async def create_application(payload: FinancingApplicationCreate, db: AsyncSession = Depends(get_db)):
    return await submit_application(
        db,
        payload.customer_id,
        payload.quote_id,
        payload.term_months,
        payload.has_existing_logbook_loan,
        payload.logbook_loan_age_months,
        payload.is_corporate,
    )


@router.post("/applications/{application_id}/documents", response_model=FinancingDocumentOut)
async def upload_document(
    application_id: str, document_type: str, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)
):
    """Attach one of the required documents (application_form, logbook,
    national_id or certificate_of_incorporation, kra_pin, premium_quote) to
    a financing application - open to the customer, matching the same
    no-auth-required document upload on the insurance application flow."""
    return await upload_financing_document(db, application_id, document_type, file)


@router.get("/applications/{application_id}/status", response_model=FinancingApplicationOut)
async def get_status(application_id: str, db: AsyncSession = Depends(get_db)):
    application = await db.get(FinancingApplication, application_id)
    if not application:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Financing application not found")
    return application


@router.get("/applications/{application_id}/agreement", response_model=FinancingAgreementOut)
async def get_agreement(application_id: str, db: AsyncSession = Depends(get_db)):
    agreement = await db.scalar(select(FinancingAgreement).where(FinancingAgreement.application_id == application_id))
    if not agreement:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No agreement yet for this application")

    installments = (
        await db.scalars(
            select(FinancingInstallment)
            .where(FinancingInstallment.agreement_id == agreement.id)
            .order_by(FinancingInstallment.installment_number)
        )
    ).all()

    return FinancingAgreementOut(
        id=str(agreement.id),
        application_id=str(agreement.application_id),
        financed_amount=agreement.financed_amount,
        interest_rate_monthly=agreement.interest_rate_monthly,
        total_repayable=agreement.total_repayable,
        term_months=agreement.term_months,
        monthly_installment=agreement.monthly_installment,
        status=agreement.status,
        installments=[InstallmentOut.model_validate(i) for i in installments],
    )


# --- Admin portfolio view ---

admin_router = APIRouter(
    prefix="/api/v1/admin/financing",
    tags=["financing"],
    dependencies=[Depends(require_roles("super_admin", "finance_officer", "management"))],
)


@admin_router.get("/applications", response_model=list[FinancingApplicationOut])
async def list_applications(db: AsyncSession = Depends(get_db), status_filter: str | None = None):
    stmt = select(FinancingApplication).order_by(FinancingApplication.created_at.desc())
    if status_filter:
        stmt = stmt.where(FinancingApplication.status == status_filter)
    return (await db.scalars(stmt)).all()


@admin_router.get("/installments/overdue", response_model=list[InstallmentOut])
async def list_overdue_installments(db: AsyncSession = Depends(get_db)):
    return (
        await db.scalars(
            select(FinancingInstallment).where(
                FinancingInstallment.status == "pending", FinancingInstallment.due_date < date.today()
            )
        )
    ).all()


@admin_router.post("/installments/{installment_id}/mark-paid", response_model=InstallmentOut)
async def mark_installment_paid(installment_id: str, db: AsyncSession = Depends(get_db)):
    installment = await db.get(FinancingInstallment, installment_id)
    if not installment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Installment not found")
    installment.status = "paid"
    installment.paid_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(installment)
    return installment


@admin_router.get("/applications/{application_id}", response_model=FinancingApplicationDetailOut)
async def get_application(application_id: str, db: AsyncSession = Depends(get_db)):
    """Full detail view - customer, quote, deposit/term/interest terms,
    documents, and decision history - so staff have everything needed to
    decide the application in one place, same as the insurance
    applications detail view."""
    return await get_financing_application_detail(db, application_id)


@admin_router.post("/applications/{application_id}/transition", response_model=FinancingApplicationOut)
async def transition(
    application_id: str,
    payload: FinancingTransitionRequest,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(get_current_claims),
):
    """Decide a financing application: approve or reject it, or - only for
    management/super_admin - approve one the credit provider auto-rejected,
    optionally at a different interest rate than the standard 3.5%/3%."""
    if payload.interest_rate_monthly is not None and claims.get("role") not in ("management", "super_admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only management can approve a non-standard interest rate")
    return await transition_financing_application(
        db, application_id, payload.to_status, claims.get("sub"), payload.notes, payload.interest_rate_monthly
    )


@admin_router.get("/applications/{application_id}/documents/{document_id}/url")
async def get_application_document_link(application_id: str, document_id: str, db: AsyncSession = Depends(get_db)):
    """A short-lived signed URL so staff can open an uploaded document."""
    url = await get_financing_document_url(db, application_id, document_id)
    return {"url": url}


@admin_router.get("/settings", response_model=FinancingSettingsOut)
async def get_settings(db: AsyncSession = Depends(get_db)):
    """The live deposit/term/interest/fee configuration every new
    eligibility check and application uses - editable below, not hardcoded.
    Readable by any financing admin role; only management/super_admin may
    change it (see the PATCH below)."""
    return await get_financing_settings(db)


@admin_router.patch("/settings", response_model=FinancingSettingsOut)
async def patch_settings(
    payload: FinancingSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(get_current_claims),
):
    """Change the deposit percentage, interest rates, term bounds, the
    three fees, or the existing-logbook-loan concession window. Only
    affects applications assessed after this change - every existing
    FinancingApplication keeps the rates it was actually given."""
    if claims.get("role") not in ("management", "super_admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only management can change financing settings")
    return await update_financing_settings(db, payload, claims.get("sub"))