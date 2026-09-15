import random
import string
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from dateutil.relativedelta import relativedelta
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.financing.registry import get_credit_provider
from app.models.customer import Customer
from app.models.financing import FinancingAgreement, FinancingApplication, FinancingInstallment
from app.models.quote import Quote

# Matches the spec §14 worked example exactly: 20% deposit, 80% financed.
DEFAULT_DEPOSIT_PERCENTAGE = Decimal("20.00")
MIN_TERM_MONTHS = 1
MAX_TERM_MONTHS = 10


def generate_financing_reference() -> str:
    year = date.today().year
    suffix = "".join(random.choices(string.digits, k=6))
    return f"SOM-FIN-{year}-{suffix}"


async def check_eligibility(db: AsyncSession, customer_id: str, quote_id: str, term_months: int) -> dict:
    if not (MIN_TERM_MONTHS <= term_months <= MAX_TERM_MONTHS):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Term must be between {MIN_TERM_MONTHS} and {MAX_TERM_MONTHS} months")

    customer = await db.get(Customer, customer_id)
    quote = await db.get(Quote, quote_id)
    if not customer or not quote:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer or quote not found")

    deposit = (quote.total * DEFAULT_DEPOSIT_PERCENTAGE / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    financed_amount = quote.total - deposit

    provider = get_credit_provider()
    result = await provider.check_eligibility(
        customer_context={"customer_id": str(customer.id), "phone": customer.phone}, amount=financed_amount
    )

    monthly_installment = (financed_amount / term_months).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if result.eligible else None

    return {
        "eligible": result.eligible,
        "reason": result.reason,
        "total_premium": quote.total,
        "deposit_percentage": DEFAULT_DEPOSIT_PERCENTAGE,
        "deposit_amount": deposit,
        "financed_amount": financed_amount,
        "term_months": term_months,
        "monthly_installment": monthly_installment,
        "is_mock": result.is_mock,
    }


async def submit_application(db: AsyncSession, customer_id: str, quote_id: str, term_months: int) -> FinancingApplication:
    eligibility = await check_eligibility(db, customer_id, quote_id, term_months)
    if not eligibility["eligible"]:
        raise HTTPException(status.HTTP_409_CONFLICT, eligibility["reason"] or "Not eligible for financing")

    customer = await db.get(Customer, customer_id)
    quote = await db.get(Quote, quote_id)

    application = FinancingApplication(
        reference=generate_financing_reference(),
        customer_id=customer_id,
        quote_id=quote_id,
        total_premium=quote.total,
        deposit_percentage=eligibility["deposit_percentage"],
        deposit_amount=eligibility["deposit_amount"],
        financed_amount=eligibility["financed_amount"],
        term_months=term_months,
        status="submitted",
    )
    db.add(application)
    await db.flush()

    provider = get_credit_provider()
    result = await provider.submit_application(
        application_reference=application.reference,
        customer_context={"customer_id": str(customer.id), "phone": customer.phone},
        financed_amount=application.financed_amount,
        term_months=term_months,
    )
    application.provider_reference = result.provider_reference

    if result.status == "approved":
        application.status = "approved"
        await _create_agreement(db, application)
    elif result.status == "rejected":
        application.status = "rejected"
        application.rejection_reason = result.reason

    await db.commit()
    await db.refresh(application)
    return application


async def _create_agreement(db: AsyncSession, application: FinancingApplication) -> FinancingAgreement:
    monthly_installment = (application.financed_amount / application.term_months).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    agreement = FinancingAgreement(
        application_id=application.id,
        financed_amount=application.financed_amount,
        term_months=application.term_months,
        monthly_installment=monthly_installment,
        status="active",
    )
    db.add(agreement)
    await db.flush()

    today = date.today()
    remaining = application.financed_amount
    for i in range(1, application.term_months + 1):
        # Last installment absorbs any rounding remainder so the schedule
        # sums exactly to financed_amount.
        amount = monthly_installment if i < application.term_months else remaining
        remaining -= monthly_installment
        db.add(
            FinancingInstallment(
                agreement_id=agreement.id,
                installment_number=i,
                due_date=today + relativedelta(months=i),
                amount=amount,
                status="pending",
            )
        )

    return agreement
