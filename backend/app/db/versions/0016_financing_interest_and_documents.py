"""financing interest, documents, and decision history

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-26
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # New columns on financing_applications. Added nullable first so
    # existing rows (already-issued agreements, computed under the old
    # zero-interest model) aren't silently reinterpreted as carrying the
    # new 3.5% default - they're explicitly backfilled at 0% below instead,
    # leaving their already-generated installment schedules mathematically
    # consistent with what's stored on them.
    op.add_column("financing_applications", sa.Column("interest_rate_monthly", sa.Numeric(5, 2), nullable=True))
    op.add_column("financing_applications", sa.Column("total_repayable", sa.Numeric(14, 2), nullable=True))
    op.add_column(
        "financing_applications",
        sa.Column("has_existing_logbook_loan", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "financing_applications", sa.Column("is_corporate", sa.Boolean, nullable=False, server_default=sa.false())
    )

    op.execute(
        "UPDATE financing_applications SET interest_rate_monthly = 0, total_repayable = financed_amount "
        "WHERE interest_rate_monthly IS NULL"
    )
    op.alter_column("financing_applications", "interest_rate_monthly", nullable=False)
    op.alter_column("financing_applications", "total_repayable", nullable=False)

    # Same backfill reasoning on financing_agreements.
    op.add_column("financing_agreements", sa.Column("interest_rate_monthly", sa.Numeric(5, 2), nullable=True))
    op.add_column("financing_agreements", sa.Column("total_repayable", sa.Numeric(14, 2), nullable=True))
    op.execute(
        "UPDATE financing_agreements SET interest_rate_monthly = 0, total_repayable = financed_amount "
        "WHERE interest_rate_monthly IS NULL"
    )
    op.alter_column("financing_agreements", "interest_rate_monthly", nullable=False)
    op.alter_column("financing_agreements", "total_repayable", nullable=False)

    op.create_table(
        "financing_documents",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "financing_application_id", pg.UUID(as_uuid=True), sa.ForeignKey("financing_applications.id"), nullable=False
        ),
        sa.Column("document_type", sa.String(50)),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), server_default="uploaded"),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_financing_documents_application_id", "financing_documents", ["financing_application_id"])

    op.create_table(
        "financing_events",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "financing_application_id", pg.UUID(as_uuid=True), sa.ForeignKey("financing_applications.id"), nullable=False
        ),
        sa.Column("event_type", sa.String(30)),
        sa.Column("from_status", sa.String(30)),
        sa.Column("to_status", sa.String(30)),
        sa.Column("notes", sa.String(2000)),
        sa.Column("actor_user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_financing_events_application_id", "financing_events", ["financing_application_id"])


def downgrade() -> None:
    op.drop_table("financing_events")
    op.drop_table("financing_documents")
    op.drop_column("financing_agreements", "total_repayable")
    op.drop_column("financing_agreements", "interest_rate_monthly")
    op.drop_column("financing_applications", "is_corporate")
    op.drop_column("financing_applications", "has_existing_logbook_loan")
    op.drop_column("financing_applications", "total_repayable")
    op.drop_column("financing_applications", "interest_rate_monthly")