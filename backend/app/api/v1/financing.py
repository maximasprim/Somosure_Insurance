from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_roles
from app.models.financing import FinancingAgreement, FinancingApplication, FinancingInstallment
from app.schemas.financing import (
    EligibilityOut,
    EligibilityRequest,
    FinancingAgreementOut,
    FinancingApplicationCreate,
    FinancingApplicationOut,
    InstallmentOut,
)
from app.services.financing_service import check_eligibility, submit_application

router = APIRouter(prefix="/api/v1/financing", tags=["financing"])


@router.post("/eligibility", response_model=EligibilityOut)
async def eligibility(payload: EligibilityRequest, db: AsyncSession = Depends(get_db)):
    return await check_eligibility(db, payload.customer_id, payload.quote_id, payload.term_months)


@router.post("/applications", response_model=FinancingApplicationOut)
async def create_application(payload: FinancingApplicationCreate, db: AsyncSession = Depends(get_db)):
    return await submit_application(db, payload.customer_id, payload.quote_id, payload.term_months)


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
