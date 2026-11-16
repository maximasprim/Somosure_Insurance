"""The sales ledger: what the weekly report workbook says was sold, claimed and financed.

These tables are deliberately separate from policies/applications/quotes. A sale recorded in
the workbook has no quote and no application behind it, and pushing it through those tables
would invent them, distort conversion figures and could fire renewal/sticker automations on
old business. The ledger sits beside the live tables; where a ledger row's policy number matches
a policy that exists in the app, `policy_id` links the two.

Everything here is written by the importer (app/services/sales_import). Rows follow the sheet:
a later upload updates them, and a row that vanishes from the sheet is marked
`missing_from_sheet`, never deleted.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ImportBatch(Base):
    """One committed upload of the workbook."""

    __tablename__ = "import_batches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(30), default="sales_workbook")
    filename: Mapped[str | None] = mapped_column(String(255))
    file_sha256: Mapped[str] = mapped_column(String(64), index=True)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="committed")
    years: Mapped[list | None] = mapped_column(JSON)
    counts: Mapped[dict | None] = mapped_column(JSON)
    summary: Mapped[dict | None] = mapped_column(JSON)  # reconciliation, issue counts, the changes made
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SalesEntry(Base):
    __tablename__ = "sales_entries"
    __table_args__ = (
        Index("ix_sales_entries_period", "period_year", "period_month"),
        Index("ix_sales_entries_sheet_year", "sheet_year"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    natural_key: Mapped[str] = mapped_column(String(64), unique=True)
    fallback_key: Mapped[str | None] = mapped_column(String(64), index=True)

    sheet_name: Mapped[str] = mapped_column(String(60))
    sheet_year: Mapped[int] = mapped_column(Integer)
    sheet_row: Mapped[int | None] = mapped_column(Integer)
    period_year: Mapped[int] = mapped_column(Integer)
    period_month: Mapped[int | None] = mapped_column(Integer)

    client_name: Mapped[str] = mapped_column(String(200))
    client_key: Mapped[str | None] = mapped_column(String(200), index=True)
    phone: Mapped[str | None] = mapped_column(String(20))
    underwriter_raw: Mapped[str | None] = mapped_column(String(120))
    underwriter: Mapped[str | None] = mapped_column(String(80), index=True)
    provider_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("insurance_providers.id"), nullable=True)

    reg_no: Mapped[str | None] = mapped_column(String(20), index=True)
    asset_ref: Mapped[str | None] = mapped_column(String(120))
    product_line: Mapped[str] = mapped_column(String(40), default="motor")

    start_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date, index=True)
    date_paid: Mapped[date | None] = mapped_column(Date)

    staff_raw: Mapped[str | None] = mapped_column(String(160))
    staff_name: Mapped[str | None] = mapped_column(String(80), index=True)
    branch: Mapped[str | None] = mapped_column(String(60), index=True)
    business_type: Mapped[str | None] = mapped_column(String(20))
    policy_number: Mapped[str | None] = mapped_column(String(80), index=True)
    cover_type: Mapped[str | None] = mapped_column(String(30))

    premium: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    commission: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    wht: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    net_revenue: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    commission_rate: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))

    flags: Mapped[list | None] = mapped_column(JSON)
    issue_level: Mapped[str] = mapped_column(String(10), default="none")  # none | info | warning | error
    raw: Mapped[dict | None] = mapped_column(JSON)
    # Corrections a person made that the sheet does not (yet) hold: an accepted date fix, or a phone number the sheet
    # lacks - {"start_date": {"value": "2026-03-14", "sheet": "2027-03-14"}}, {"phone": {"value": "+2547...", "sheet": null}}.
    # A correction holds while the sheet still says `sheet`; once the sheet cell changes, the sheet wins again.
    overrides: Mapped[dict | None] = mapped_column(JSON)

    status: Mapped[str] = mapped_column(String(20), default="active")  # active | missing_from_sheet
    # Where the row came from: "workbook" (an import) or "manual" (a sale recorded directly in the system). A manual row
    # is never marked missing from the sheet - it may simply not be in the sheet - but if the same sale does appear in
    # the sheet later, the sheet row is recognised as the same sale and merged into it.
    origin: Mapped[str] = mapped_column(String(20), default="workbook", server_default="workbook")
    entered_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    policy_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("policies.id"), nullable=True)
    # The customer this sale belongs to, when it could be matched (policy, phone or plate) or created on request.
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True, index=True)
    # Renewal follow-up kept by staff. Never touched by an import, so it survives every re-upload.
    follow_up_status: Mapped[str | None] = mapped_column(String(20))  # contacted | quoted | renewed | lost; empty = still due
    follow_up_note: Mapped[str | None] = mapped_column(Text)
    follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    follow_up_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    # Set when this row has been posted into the system's own tables (see services/sales_import/posting.py): the
    # records created for it, so they can be kept in step with the sheet and, if needed, removed again.
    quote_request_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("quote_requests.id"), nullable=True)
    quote_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("quotes.id"), nullable=True)
    application_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("applications.id"), nullable=True)
    payment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("payments.id"), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    post_flags: Mapped[list | None] = mapped_column(JSON)  # what to review on the posted records
    first_batch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("import_batches.id"), nullable=True)
    last_batch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("import_batches.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class LegacyClaim(Base):
    """A claim line from a 'Claims YYYY' sheet, with its narrative and the dated steps read out of it."""

    __tablename__ = "legacy_claims"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    natural_key: Mapped[str] = mapped_column(String(64), unique=True)
    sheet_name: Mapped[str] = mapped_column(String(60))
    sheet_row: Mapped[int | None] = mapped_column(Integer)
    period_year: Mapped[int] = mapped_column(Integer, index=True)

    client_name: Mapped[str] = mapped_column(String(200))
    client_key: Mapped[str | None] = mapped_column(String(200), index=True)
    contact: Mapped[str | None] = mapped_column(String(20))
    reg_or_policy: Mapped[str | None] = mapped_column(String(120))
    reg_no: Mapped[str | None] = mapped_column(String(20), index=True)
    underwriter_raw: Mapped[str | None] = mapped_column(String(120))
    underwriter: Mapped[str | None] = mapped_column(String(80))
    provider_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("insurance_providers.id"), nullable=True)
    date_reported: Mapped[date | None] = mapped_column(Date)
    narrative: Mapped[str | None] = mapped_column(Text)
    outcome_raw: Mapped[str | None] = mapped_column(String(120))
    outcome: Mapped[str] = mapped_column(String(30), default="open")  # open | closed | closed_unresponsive | action_needed
    milestones: Mapped[list | None] = mapped_column(JSON)

    sales_entry_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_entries.id"), nullable=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True, index=True)
    flags: Mapped[list | None] = mapped_column(JSON)
    issue_level: Mapped[str] = mapped_column(String(10), default="none")
    raw: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="active")
    first_batch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("import_batches.id"), nullable=True)
    last_batch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("import_batches.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class IpfRemittance(Base):
    """A line from the 'IPF REPORT YYYY' sheet: premium paid to an insurer on a financed policy."""

    __tablename__ = "ipf_remittances"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    natural_key: Mapped[str] = mapped_column(String(64), unique=True)
    sheet_name: Mapped[str] = mapped_column(String(60))
    sheet_row: Mapped[int | None] = mapped_column(Integer)
    period_year: Mapped[int] = mapped_column(Integer, index=True)

    underwriter_raw: Mapped[str | None] = mapped_column(String(120))
    underwriter: Mapped[str | None] = mapped_column(String(80))
    provider_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("insurance_providers.id"), nullable=True)
    details: Mapped[str | None] = mapped_column(String(255))
    date_paid: Mapped[date | None] = mapped_column(Date)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))

    flags: Mapped[list | None] = mapped_column(JSON)
    issue_level: Mapped[str] = mapped_column(String(10), default="none")
    raw: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="active")
    first_batch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("import_batches.id"), nullable=True)
    last_batch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("import_batches.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ImportAlias(Base):
    """How a name as typed in the sheet maps to the name the app uses.

    kind 'underwriter': canonical is the insurer name ('MORNACH' -> 'MONARCH').
    kind 'staff': canonical is the staff name and branch the branch ('JOSPHINE -HQ' -> Josphine / HQ).
    Aliases the importer worked out itself are saved unconfirmed so an administrator can review
    them once; once saved, an alias always wins over the importer's own guess."""

    __tablename__ = "import_aliases"
    __table_args__ = (UniqueConstraint("kind", "alias_key", name="uq_import_alias_kind_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(20))
    alias_key: Mapped[str] = mapped_column(String(200))  # upper-case, letters/digits, single spaces
    as_typed: Mapped[str | None] = mapped_column(String(200))
    canonical: Mapped[str | None] = mapped_column(String(120))
    branch: Mapped[str | None] = mapped_column(String(60))
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(20), default="auto")  # auto | admin
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class UnderwriterLink(Base):
    """Which provider in the system an underwriter written in the sheet is. 'MONARCH' in the sheet and
    'Monarch Insurance Company' in the providers list are the same insurer: this is where that is recorded."""

    __tablename__ = "underwriter_links"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    underwriter: Mapped[str] = mapped_column(String(80), unique=True)  # as the importer names it (MONARCH, DIRECT LINE...)
    provider_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("insurance_providers.id"), nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="auto")  # auto | admin | created
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
