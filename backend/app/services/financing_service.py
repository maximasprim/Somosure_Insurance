import random
import string
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from dateutil.relativedelta import relativedelta
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import ALLOWED_CONTENT_TYPES, MAX_UPLOAD_BYTES, get_storage
from app.financing.registry import get_credit_provider
from app.models.customer import Customer
from app.models.financing import (
    FINANCING_SETTINGS_ID,
    FinancingAgreement,
    FinancingApplication,
    FinancingDocument,
    FinancingEvent,
    FinancingInstallment,
    FinancingSettings,
)
from app.models.provider import InsuranceProduct, InsuranceProvider
from app.models.quote import Quote
from app.schemas.financing import (
    FinancingAgreementOut,
    FinancingApplicationDetailOut,
    FinancingCustomerOut,
    FinancingQuoteOut,
    FinancingSettingsUpdate,
    InstallmentOut,
)

# Every rate/term/fee below is a *factory default* only, used to seed
# FinancingSettings the first time it's read (see get_financing_settings).
# The live values admin staff actually see and edit come from that table,
# not these constants - see the "configurable, not hardcoded" request this
# was built for.
DEFAULT_DEPOSIT_PERCENTAGE = Decimal("20.00")
MIN_TERM_MONTHS = 4
MAX_TERM_MONTHS = 10
STANDARD_INTEREST_RATE_MONTHLY = Decimal("3.50")
PREFERRED_INTEREST_RATE_MONTHLY = Decimal("3.00")
DEFAULT_LOAN_APPLICATION_FEE_PCT = Decimal("1.00")
DEFAULT_LIFE_INSURANCE_FEE_PCT = Decimal("1.00")
# Left at 0% - Kenya's excise duty on financial-institution fees wasn't
# confirmed at the time this was built. Set the real rate in
# FinancingSettings/the admin dashboard once it is; nothing is charged
# until then.
DEFAULT_EXCISE_DUTY_PCT = Decimal("0.00")
DEFAULT_CONCESSION_LOAN_AGE_MAX_MONTHS = 3

# Every financing application needs these regardless of applicant type;
# certificate_of_incorporation replaces national_id for a corporate/company
# applicant. Checked informationally in the detail view below - not a hard
# gate on submission today, since submission is decided synchronously by
# the credit provider at creation time, before there's anywhere to attach
# documents to yet.
REQUIRED_DOCUMENT_TYPES_INDIVIDUAL = ("application_form", "logbook", "national_id", "kra_pin", "premium_quote")
REQUIRED_DOCUMENT_TYPES_CORPORATE = ("application_form", "logbook", "certificate_of_incorporation", "kra_pin", "premium_quote")

# Staff decisions available from each status - mirrors ALLOWED_STAFF_TRANSITIONS
# in application_service.py/claim_service.py. "rejected": {"approved"} is the
# management override path for an application the mock provider auto-declined.
ALLOWED_STAFF_TRANSITIONS: dict[str, set[str]] = {
    "submitted": {"approved", "rejected"},
    "rejected": {"approved"},
}


def generate_financing_reference() -> str:
    year = date.today().year
    suffix = "".join(random.choices(string.digits, k=6))
    return f"SOM-FIN-{year}-{suffix}"


async def get_financing_settings(db: AsyncSession) -> FinancingSettings:
    """The one row of admin-editable financing configuration. Created with
    factory defaults on first read if it doesn't exist yet (e.g. a database
    migrated before this table existed, or a fresh dev DB created via
    Base.metadata.create_all in tests rather than via the 0017 migration's
    seed insert)."""
    settings = await db.get(FinancingSettings, FINANCING_SETTINGS_ID)
    if not settings:
        settings = FinancingSettings(
            id=FINANCING_SETTINGS_ID,
            deposit_percentage_standard=DEFAULT_DEPOSIT_PERCENTAGE,
            interest_rate_standard_monthly=STANDARD_INTEREST_RATE_MONTHLY,
            interest_rate_preferred_monthly=PREFERRED_INTEREST_RATE_MONTHLY,
            min_term_months=MIN_TERM_MONTHS,
            max_term_months=MAX_TERM_MONTHS,
            loan_application_fee_pct=DEFAULT_LOAN_APPLICATION_FEE_PCT,
            life_insurance_fee_pct=DEFAULT_LIFE_INSURANCE_FEE_PCT,
            excise_duty_pct=DEFAULT_EXCISE_DUTY_PCT,
            concession_loan_age_max_months=DEFAULT_CONCESSION_LOAN_AGE_MAX_MONTHS,
        )
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    return settings


async def update_financing_settings(db: AsyncSession, payload: FinancingSettingsUpdate, actor_user_id: str | None) -> FinancingSettings:
    settings = await get_financing_settings(db)
    updates = payload.model_dump(exclude_unset=True)

    new_min = updates.get("min_term_months", settings.min_term_months)
    new_max = updates.get("max_term_months", settings.max_term_months)
    if new_min > new_max:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "min_term_months cannot be greater than max_term_months")

    for field, value in updates.items():
        setattr(settings, field, value)
    settings.updated_by_user_id = actor_user_id

    await db.commit()
    await db.refresh(settings)
    return settings


def _round(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _repayment_figures(financed_amount: Decimal, interest_rate_monthly: Decimal, term_months: int) -> tuple[Decimal, Decimal]:
    """Simple (flat) interest, consistent with the rest of this module's
    already-simple math: interest = principal x monthly rate x months,
    charged upfront rather than on a reducing balance. Returns
    (total_repayable, monthly_installment). Fees are handled separately in
    check_eligibility, since (unlike interest) they don't scale with the
    term - they're computed once and added to whatever this returns."""
    total_interest = _round(financed_amount * interest_rate_monthly / 100 * term_months)
    total_repayable = financed_amount + total_interest
    monthly_installment = _round(total_repayable / term_months)
    return total_repayable, monthly_installment


async def check_eligibility(
    db: AsyncSession,
    customer_id: str,
    quote_id: str,
    term_months: int,
    has_existing_logbook_loan: bool = False,
    logbook_loan_age_months: int | None = None,
) -> dict:
    settings = await get_financing_settings(db)

    if not (settings.min_term_months <= term_months <= settings.max_term_months):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Term must be between {settings.min_term_months} and {settings.max_term_months} months"
        )

    customer = await db.get(Customer, customer_id)
    quote = await db.get(Quote, quote_id)
    if not customer or not quote:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer or quote not found")

    # The full concession (waived deposit, preferred rate, waived fees)
    # only applies for an existing Bidii Credit logbook loan that's still
    # young - an existing loan older than the configured window is treated
    # the same as having none.
    concession_applied = (
        has_existing_logbook_loan
        and logbook_loan_age_months is not None
        and logbook_loan_age_months <= settings.concession_loan_age_max_months
    )

    deposit_percentage = Decimal("0.00") if concession_applied else settings.deposit_percentage_standard
    interest_rate_monthly = settings.interest_rate_preferred_monthly if concession_applied else settings.interest_rate_standard_monthly

    deposit = _round(quote.total * deposit_percentage / 100)
    financed_amount = quote.total - deposit

    provider = get_credit_provider()
    result = await provider.check_eligibility(
        customer_context={"customer_id": str(customer.id), "phone": customer.phone}, amount=financed_amount
    )

    total_repayable = monthly_installment = None
    loan_application_fee = life_insurance_fee = excise_duty_amount = Decimal("0.00")
    if result.eligible:
        if concession_applied:
            loan_application_fee_pct = life_insurance_fee_pct = excise_duty_pct = Decimal("0.00")
        else:
            loan_application_fee_pct = settings.loan_application_fee_pct
            life_insurance_fee_pct = settings.life_insurance_fee_pct
            excise_duty_pct = settings.excise_duty_pct

        loan_application_fee = _round(financed_amount * loan_application_fee_pct / 100)
        life_insurance_fee = _round(financed_amount * life_insurance_fee_pct / 100)
        # Excise duty is charged on the two fees above, not on the loan
        # principal - matching how Kenyan excise duty on financial
        # institution fees is applied in practice.
        excise_duty_amount = _round((loan_application_fee + life_insurance_fee) * excise_duty_pct / 100)

        total_repayable, monthly_installment = _repayment_figures(financed_amount, interest_rate_monthly, term_months)
        total_repayable += loan_application_fee + life_insurance_fee + excise_duty_amount
        monthly_installment = _round(total_repayable / term_months)

    return {
        "eligible": result.eligible,
        "reason": result.reason,
        "total_premium": quote.total,
        "deposit_percentage": deposit_percentage,
        "deposit_amount": deposit,
        "financed_amount": financed_amount,
        "interest_rate_monthly": interest_rate_monthly,
        "concession_applied": concession_applied,
        "loan_application_fee_pct": loan_application_fee_pct if result.eligible else settings.loan_application_fee_pct,
        "loan_application_fee": loan_application_fee,
        "life_insurance_fee_pct": life_insurance_fee_pct if result.eligible else settings.life_insurance_fee_pct,
        "life_insurance_fee": life_insurance_fee,
        "excise_duty_pct": excise_duty_pct if result.eligible else settings.excise_duty_pct,
        "excise_duty_amount": excise_duty_amount,
        "total_repayable": total_repayable,
        "term_months": term_months,
        "monthly_installment": monthly_installment,
        "is_mock": result.is_mock,
    }


async def submit_application(
    db: AsyncSession,
    customer_id: str,
    quote_id: str,
    term_months: int,
    has_existing_logbook_loan: bool = False,
    logbook_loan_age_months: int | None = None,
    is_corporate: bool = False,
) -> FinancingApplication:
    eligibility = await check_eligibility(db, customer_id, quote_id, term_months, has_existing_logbook_loan, logbook_loan_age_months)
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
        interest_rate_monthly=eligibility["interest_rate_monthly"],
        concession_applied=eligibility["concession_applied"],
        loan_application_fee_pct=eligibility["loan_application_fee_pct"],
        loan_application_fee=eligibility["loan_application_fee"],
        life_insurance_fee_pct=eligibility["life_insurance_fee_pct"],
        life_insurance_fee=eligibility["life_insurance_fee"],
        excise_duty_pct=eligibility["excise_duty_pct"],
        excise_duty_amount=eligibility["excise_duty_amount"],
        total_repayable=eligibility["total_repayable"],
        term_months=term_months,
        has_existing_logbook_loan=has_existing_logbook_loan,
        logbook_loan_age_months=logbook_loan_age_months,
        is_corporate=is_corporate,
        status="submitted",
    )
    db.add(application)
    await db.flush()
    db.add(FinancingEvent(financing_application_id=application.id, event_type="status_changed", to_status="submitted"))

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
        db.add(
            FinancingEvent(
                financing_application_id=application.id, event_type="status_changed", from_status="submitted", to_status="approved"
            )
        )
        await _create_agreement(db, application)
    elif result.status == "rejected":
        application.status = "rejected"
        application.rejection_reason = result.reason
        db.add(
            FinancingEvent(
                financing_application_id=application.id,
                event_type="status_changed",
                from_status="submitted",
                to_status="rejected",
                notes=result.reason,
            )
        )

    await db.commit()
    await db.refresh(application)
    return application


async def _create_agreement(db: AsyncSession, application: FinancingApplication) -> FinancingAgreement:
    agreement = FinancingAgreement(
        application_id=application.id,
        financed_amount=application.financed_amount,
        interest_rate_monthly=application.interest_rate_monthly,
        total_repayable=application.total_repayable,
        term_months=application.term_months,
        monthly_installment=_round(application.total_repayable / application.term_months),
        status="active",
    )
    db.add(agreement)
    await db.flush()

    today = date.today()
    remaining = application.total_repayable
    for i in range(1, application.term_months + 1):
        # Last installment absorbs any rounding remainder so the schedule
        # sums exactly to total_repayable (principal + interest + fees).
        amount = agreement.monthly_installment if i < application.term_months else remaining
        remaining -= agreement.monthly_installment
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


async def transition_financing_application(
    db: AsyncSession,
    application_id: str,
    to_status: str,
    actor_user_id: str | None,
    notes: str | None,
    interest_rate_monthly_override: Decimal | None = None,
) -> FinancingApplication:
    """The admin decision behind the financing review screen: approve or
    reject a submitted application, or - as a management-approved exception
    - approve one the credit provider auto-rejected, optionally at a
    different interest rate than the standard/preferred rates. Only the
    interest rate is overridable this way; the fees already assessed at
    application time are left as they were. Every decision is recorded on
    FinancingEvent. Does not touch submit_application above, which still
    runs its own automatic provider decision unchanged."""
    application = await db.get(FinancingApplication, application_id)
    if not application:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Financing application not found")

    allowed = ALLOWED_STAFF_TRANSITIONS.get(application.status, set())
    if to_status not in allowed:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Cannot move financing application from '{application.status}' to '{to_status}' - allowed next steps: {sorted(allowed) or 'none'}",
        )

    from_status = application.status

    if to_status == "approved":
        if interest_rate_monthly_override is not None:
            application.interest_rate_monthly = interest_rate_monthly_override
            total_repayable, _ = _repayment_figures(application.financed_amount, application.interest_rate_monthly, application.term_months)
            application.total_repayable = total_repayable + application.loan_application_fee + application.life_insurance_fee + application.excise_duty_amount
            db.add(
                FinancingEvent(
                    financing_application_id=application.id,
                    event_type="rate_override",
                    notes=f"Rate set to {interest_rate_monthly_override}%/month by management approval"
                    + (f": {notes}" if notes else ""),
                )
            )
        application.status = "approved"
        application.rejection_reason = None
        # A rejected application won't have an agreement yet; an already-
        # submitted-then-approved one won't either (agreements are only
        # created here or in submit_application's own approval branch).
        existing_agreement = await db.scalar(select(FinancingAgreement).where(FinancingAgreement.application_id == application.id))
        if not existing_agreement:
            await _create_agreement(db, application)
    else:
        application.status = to_status
        if to_status == "rejected":
            application.rejection_reason = notes

    db.add(
        FinancingEvent(
            financing_application_id=application.id,
            event_type="status_changed",
            from_status=from_status,
            to_status=to_status,
            notes=notes,
            actor_user_id=actor_user_id,
        )
    )

    await db.commit()
    await db.refresh(application)
    return application


async def upload_financing_document(
    db: AsyncSession, application_id: str, document_type: str, file: UploadFile
) -> FinancingDocument:
    application = await db.get(FinancingApplication, application_id)
    if not application:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Financing application not found")

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Only PDF, JPEG, or PNG documents are accepted")

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File exceeds the 10MB limit")

    storage = get_storage()
    storage_path = await storage.save(f"financing/{application_id}", file.filename or "document", content)

    doc = FinancingDocument(
        financing_application_id=application.id,
        document_type=document_type,
        storage_path=storage_path,
        original_filename=file.filename or "document",
        content_type=file.content_type,
        size_bytes=len(content),
        status="uploaded",
    )
    db.add(doc)
    db.add(
        FinancingEvent(
            financing_application_id=application.id,
            event_type="document_uploaded",
            notes=f"Uploaded {document_type.replace('_', ' ')}",
        )
    )

    await db.commit()
    await db.refresh(doc)
    return doc


async def get_financing_document_url(db: AsyncSession, application_id: str, document_id: str) -> str:
    document = await db.get(FinancingDocument, document_id)
    if not document or str(document.financing_application_id) != str(application_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found on this financing application")

    storage = get_storage()
    return await storage.get_signed_url(document.storage_path)


async def get_financing_application_detail(db: AsyncSession, application_id: str) -> FinancingApplicationDetailOut:
    """Everything staff need on one screen to decide a financing
    application: the customer, the quote it's financing, the deposit/term/
    interest/fee terms, every uploaded document, the full decision history,
    and the resulting agreement/installment schedule if one exists yet."""
    application = await db.get(FinancingApplication, application_id)
    if not application:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Financing application not found")

    customer = await db.get(Customer, application.customer_id)
    if not customer:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer on this application no longer exists")

    quote = await db.get(Quote, application.quote_id)
    if not quote:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Quote on this application no longer exists")
    provider = await db.get(InsuranceProvider, quote.provider_id)
    product = await db.get(InsuranceProduct, quote.product_id) if quote.product_id else None

    documents = (
        await db.scalars(
            select(FinancingDocument)
            .where(FinancingDocument.financing_application_id == application.id)
            .order_by(FinancingDocument.uploaded_at.asc())
        )
    ).all()
    events = (
        await db.scalars(
            select(FinancingEvent)
            .where(FinancingEvent.financing_application_id == application.id)
            .order_by(FinancingEvent.created_at.desc())
        )
    ).all()

    agreement_row = await db.scalar(select(FinancingAgreement).where(FinancingAgreement.application_id == application.id))
    agreement_out = None
    if agreement_row:
        installments = (
            await db.scalars(
                select(FinancingInstallment)
                .where(FinancingInstallment.agreement_id == agreement_row.id)
                .order_by(FinancingInstallment.installment_number)
            )
        ).all()
        agreement_out = FinancingAgreementOut(
            id=agreement_row.id,
            application_id=agreement_row.application_id,
            financed_amount=agreement_row.financed_amount,
            interest_rate_monthly=agreement_row.interest_rate_monthly,
            total_repayable=agreement_row.total_repayable,
            term_months=agreement_row.term_months,
            monthly_installment=agreement_row.monthly_installment,
            status=agreement_row.status,
            installments=[InstallmentOut.model_validate(i) for i in installments],
        )

    return FinancingApplicationDetailOut(
        id=application.id,
        reference=application.reference,
        status=application.status,
        customer=FinancingCustomerOut.model_validate(customer),
        quote=FinancingQuoteOut(
            id=quote.id,
            provider_name=provider.name if provider else "Unknown provider",
            product_name=product.name if product else None,
            premium=quote.premium,
            total=quote.total,
            currency=quote.currency,
        ),
        total_premium=application.total_premium,
        deposit_percentage=application.deposit_percentage,
        deposit_amount=application.deposit_amount,
        financed_amount=application.financed_amount,
        interest_rate_monthly=application.interest_rate_monthly,
        concession_applied=application.concession_applied,
        loan_application_fee_pct=application.loan_application_fee_pct,
        loan_application_fee=application.loan_application_fee,
        life_insurance_fee_pct=application.life_insurance_fee_pct,
        life_insurance_fee=application.life_insurance_fee,
        excise_duty_pct=application.excise_duty_pct,
        excise_duty_amount=application.excise_duty_amount,
        total_repayable=application.total_repayable,
        term_months=application.term_months,
        has_existing_logbook_loan=application.has_existing_logbook_loan,
        logbook_loan_age_months=application.logbook_loan_age_months,
        is_corporate=application.is_corporate,
        provider_reference=application.provider_reference,
        rejection_reason=application.rejection_reason,
        created_at=application.created_at,
        updated_at=application.updated_at,
        documents=documents,
        events=events,
        agreement=agreement_out,
    )