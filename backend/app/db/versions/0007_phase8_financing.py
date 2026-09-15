"""phase 8 - premium financing (bidii credit)

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-05
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "financing_applications",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("reference", sa.String(30), nullable=False, unique=True),
        sa.Column("customer_id", pg.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("quote_id", pg.UUID(as_uuid=True), sa.ForeignKey("quotes.id"), nullable=False),
        sa.Column("total_premium", sa.Numeric(14, 2)),
        sa.Column("deposit_percentage", sa.Numeric(5, 2)),
        sa.Column("deposit_amount", sa.Numeric(14, 2)),
        sa.Column("financed_amount", sa.Numeric(14, 2)),
        sa.Column("term_months", sa.Integer),
        sa.Column("status", sa.String(30), server_default="eligibility_checked"),
        sa.Column("provider_reference", sa.String(100)),
        sa.Column("rejection_reason", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "financing_agreements",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "application_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("financing_applications.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("policy_id", pg.UUID(as_uuid=True), sa.ForeignKey("policies.id"), nullable=True),
        sa.Column("financed_amount", sa.Numeric(14, 2)),
        sa.Column("term_months", sa.Integer),
        sa.Column("monthly_installment", sa.Numeric(14, 2)),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "financing_installments",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("agreement_id", pg.UUID(as_uuid=True), sa.ForeignKey("financing_agreements.id"), nullable=False),
        sa.Column("installment_number", sa.Integer),
        sa.Column("due_date", sa.Date),
        sa.Column("amount", sa.Numeric(14, 2)),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_financing_installments_agreement_id", "financing_installments", ["agreement_id"])


def downgrade() -> None:
    op.drop_table("financing_installments")
    op.drop_table("financing_agreements")
    op.drop_table("financing_applications")
