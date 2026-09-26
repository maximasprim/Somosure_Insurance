import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# Lifecycle from spec §14.
FINANCING_APPLICATION_STATUSES = ("eligibility_checked", "submitted", "approved", "rejected", "cancelled")
FINANCING_AGREEMENT_STATUSES = ("active", "completed", "defaulted", "cancelled")
INSTALLMENT_STATUSES = ("pending", "paid", "overdue", "waived")


class FinancingApplication(Base):
    """One request to finance a premium - kept entirely separate from the
    Policy/Application it funds, per spec §14's rule that financing must
    never alter insurance policy terms. Links to a Quote (the premium being
    financed), not a Policy, since eligibility is checked before a policy
    exists."""

    __tablename__ = "financing_applications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reference: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"))
    quote_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("quotes.id"))

    total_premium: Mapped[Numeric] = mapped_column(Numeric(14, 2))
    deposit_percentage: Mapped[Numeric] = mapped_column(Numeric(5, 2))
    deposit_amount: Mapped[Numeric] = mapped_column(Numeric(14, 2))
    financed_amount: Mapped[Numeric] = mapped_column(Numeric(14, 2))
    term_months: Mapped[int] = mapped_column(Integer)

    # Interest, added alongside the deposit/term rules above: 3.5%/month is
    # the standard rate; 3%/month applies for a customer with an existing
    # Bidii Credit logbook loan (the same relationship that waives the
    # deposit below). interest_rate_monthly/total_repayable are the actual
    # figures used for this application's schedule - not recomputed later
    # if the standard/preferred rates ever change, and separately
    # overridable per-application by management (see ALLOWED_STAFF_TRANSITIONS
    # in financing_service.py) for an approved exception.
    interest_rate_monthly: Mapped[Numeric] = mapped_column(Numeric(5, 2), default=Decimal("3.50"))
    total_repayable: Mapped[Numeric] = mapped_column(Numeric(14, 2))
    # financed_amount + total interest over the term - what the installment
    # schedule actually sums to.

    # An existing, active Bidii Credit logbook loan can waive the deposit,
    # apply the preferred interest rate, and waive the three fees below -
    # but only if that existing loan is still young (see
    # FinancingSettings.concession_loan_age_max_months, default 3 months).
    # An existing loan older than that is treated the same as having none:
    # full deposit, standard rate, and fees all apply. Self-declared by the
    # customer today - kept here as a record of what this application was
    # actually assessed against, not independently verified against a
    # credit bureau.
    has_existing_logbook_loan: Mapped[bool] = mapped_column(default=False)
    logbook_loan_age_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    concession_applied: Mapped[bool] = mapped_column(default=False)
    # True if has_existing_logbook_loan and logbook_loan_age_months were
    # both within the concession window at the time this application was
    # assessed - i.e. whether the deposit/rate/fee waivers above actually
    # took effect, since having an existing loan alone doesn't guarantee it.

    # Fees - all rates configurable via FinancingSettings/the admin
    # dashboard rather than hardcoded, and each is snapshotted here (rate
    # and amount) alongside interest_rate_monthly for the same audit
    # reason: so a later change to the standard rates never silently
    # reinterprets an application that already carries its own agreement
    # and installment schedule. All three are waived (0) when
    # concession_applied is True.
    loan_application_fee_pct: Mapped[Numeric] = mapped_column(Numeric(5, 2), default=Decimal("0.00"))
    loan_application_fee: Mapped[Numeric] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    life_insurance_fee_pct: Mapped[Numeric] = mapped_column(Numeric(5, 2), default=Decimal("0.00"))
    life_insurance_fee: Mapped[Numeric] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    # Kenyan excise duty on financial institution fees - charged on the two
    # fees above (application fee + life insurance fee), not on the loan
    # principal. Defaults to 0% until set in FinancingSettings, since the
    # correct current rate wasn't confirmed at the time this was built -
    # see the note in financing_service.py.
    excise_duty_pct: Mapped[Numeric] = mapped_column(Numeric(5, 2), default=Decimal("0.00"))
    excise_duty_amount: Mapped[Numeric] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))

    # Certificate of incorporation is required instead of a personal ID for
    # a corporate/company applicant - this flag is what the documents
    # checklist below keys off of.
    is_corporate: Mapped[bool] = mapped_column(default=False)

    status: Mapped[str] = mapped_column(String(30), default="eligibility_checked")
    provider_reference: Mapped[str | None] = mapped_column(String(100))
    # Bidii Credit's own reference once submitted - populated by the adapter,
    # not fabricated here.
    rejection_reason: Mapped[str | None] = mapped_column(String(500))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class FinancingAgreement(Base):
    """The signed credit agreement once an application is approved -
    deliberately its own table (not a status on FinancingApplication) so
    it's unambiguous that this is a distinct credit obligation, separate
    from the insurance policy (spec §14: 'maintain clear separation
    between insurance obligation and credit obligation')."""

    __tablename__ = "financing_agreements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("financing_applications.id"), unique=True)
    policy_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("policies.id"), nullable=True)
    financed_amount: Mapped[Numeric] = mapped_column(Numeric(14, 2))
    interest_rate_monthly: Mapped[Numeric] = mapped_column(Numeric(5, 2), default=Decimal("3.50"))
    total_repayable: Mapped[Numeric] = mapped_column(Numeric(14, 2))
    term_months: Mapped[int] = mapped_column(Integer)
    monthly_installment: Mapped[Numeric] = mapped_column(Numeric(14, 2))
    status: Mapped[str] = mapped_column(String(20), default="active")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class FinancingInstallment(Base):
    __tablename__ = "financing_installments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agreement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("financing_agreements.id"))
    installment_number: Mapped[int] = mapped_column(Integer)
    due_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Numeric] = mapped_column(Numeric(14, 2))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FinancingDocument(Base):
    """Kept as its own table rather than reusing ApplicationDocument, for
    the same reason FinancingApplication is its own table and not a status
    on Application - spec §14's "clear separation between insurance
    obligation and credit obligation" applies to the paperwork too, even
    where a document type (logbook, national ID, KRA PIN) overlaps with
    what was already uploaded for the insurance application itself."""

    __tablename__ = "financing_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    financing_application_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("financing_applications.id"))
    document_type: Mapped[str] = mapped_column(String(50))
    # application_form, logbook, national_id, kra_pin, premium_quote,
    # certificate_of_incorporation (corporate applicants only)
    storage_path: Mapped[str] = mapped_column(String(500))
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column()
    status: Mapped[str] = mapped_column(String(20), default="uploaded")
    # uploaded | verified | rejected

    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FinancingEvent(Base):
    """Append-only status/decision history for a financing application -
    mirrors ApplicationEvent/ClaimEvent so an underwriting or management
    decision (and any notes or rate exception that came with it) has the
    same permanent audit trail those already do."""

    __tablename__ = "financing_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    financing_application_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("financing_applications.id"))
    event_type: Mapped[str] = mapped_column(String(30))  # status_changed, document_uploaded, rate_override, ...
    from_status: Mapped[str | None] = mapped_column(String(30))
    to_status: Mapped[str | None] = mapped_column(String(30))
    notes: Mapped[str | None] = mapped_column(String(2000))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# The fixed id every FinancingSettings row uses - this table is a
# singleton (one row of admin-editable configuration), not a per-record
# table, so there's nothing to look up by except this constant.
FINANCING_SETTINGS_ID = "00000000-0000-0000-0000-000000000001"


class FinancingSettings(Base):
    """Every number in the Bidii Credit financing rules that used to be a
    hardcoded constant in financing_service.py, moved here so admin staff
    can change them from the dashboard without a code deploy. Always
    exactly one row (id=FINANCING_SETTINGS_ID) - get_financing_settings()
    in financing_service.py creates it with these defaults on first read
    if it doesn't exist yet.

    Changing a value here only affects applications assessed *after* the
    change - every FinancingApplication snapshots the rates it was actually
    given (interest_rate_monthly, loan_application_fee_pct, etc.), so past
    applications and their agreements/installment schedules are never
    silently reinterpreted."""

    __tablename__ = "financing_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    deposit_percentage_standard: Mapped[Numeric] = mapped_column(Numeric(5, 2), default=Decimal("20.00"))
    interest_rate_standard_monthly: Mapped[Numeric] = mapped_column(Numeric(5, 2), default=Decimal("3.50"))
    interest_rate_preferred_monthly: Mapped[Numeric] = mapped_column(Numeric(5, 2), default=Decimal("3.00"))
    min_term_months: Mapped[int] = mapped_column(Integer, default=4)
    max_term_months: Mapped[int] = mapped_column(Integer, default=10)

    # The three fees you asked to make configurable. excise_duty_pct
    # defaults to 0 (not the ~20% Kenya has historically applied to
    # financial-institution fees under the Excise Duty Act) since that
    # figure wasn't confirmed - set it here once it is, rather than this
    # code silently assuming a tax rate on your behalf.
    loan_application_fee_pct: Mapped[Numeric] = mapped_column(Numeric(5, 2), default=Decimal("1.00"))
    life_insurance_fee_pct: Mapped[Numeric] = mapped_column(Numeric(5, 2), default=Decimal("1.00"))
    excise_duty_pct: Mapped[Numeric] = mapped_column(Numeric(5, 2), default=Decimal("0.00"))

    # How recent an existing Bidii Credit logbook loan must be for the
    # deposit/rate/fee concessions to apply at all.
    concession_loan_age_max_months: Mapped[int] = mapped_column(Integer, default=3)

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)