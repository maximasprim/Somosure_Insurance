"""financing settings (configurable fees/rates) and fee tracking

Revision ID: 0017
Revises: 0016
Create Date: 2026-09-26
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None

FINANCING_SETTINGS_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    op.create_table(
        "financing_settings",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("deposit_percentage_standard", sa.Numeric(5, 2), server_default="20.00"),
        sa.Column("interest_rate_standard_monthly", sa.Numeric(5, 2), server_default="3.50"),
        sa.Column("interest_rate_preferred_monthly", sa.Numeric(5, 2), server_default="3.00"),
        sa.Column("min_term_months", sa.Integer, server_default="4"),
        sa.Column("max_term_months", sa.Integer, server_default="10"),
        sa.Column("loan_application_fee_pct", sa.Numeric(5, 2), server_default="1.00"),
        sa.Column("life_insurance_fee_pct", sa.Numeric(5, 2), server_default="1.00"),
        # Left at 0% deliberately - the real current rate wasn't confirmed.
        # Set this from the admin dashboard once it is.
        sa.Column("excise_duty_pct", sa.Numeric(5, 2), server_default="0.00"),
        sa.Column("concession_loan_age_max_months", sa.Integer, server_default="3"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_by_user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )
    op.execute(f"INSERT INTO financing_settings (id) VALUES ('{FINANCING_SETTINGS_ID}')")

    # New columns on financing_applications: the fee snapshot for each
    # application (rate + amount, same pattern as interest_rate_monthly),
    # plus the concession-eligibility fields the 3-month rule needs.
    # Nullable-then-backfill for the same reason as the 0016 migration -
    # existing rows predate fees entirely, so they're backfilled at 0
    # (no fee), not reinterpreted under today's default 1%/1%/0% rates.
    op.add_column("financing_applications", sa.Column("logbook_loan_age_months", sa.Integer, nullable=True))
    op.add_column("financing_applications", sa.Column("concession_applied", sa.Boolean, nullable=True))
    op.add_column("financing_applications", sa.Column("loan_application_fee_pct", sa.Numeric(5, 2), nullable=True))
    op.add_column("financing_applications", sa.Column("loan_application_fee", sa.Numeric(14, 2), nullable=True))
    op.add_column("financing_applications", sa.Column("life_insurance_fee_pct", sa.Numeric(5, 2), nullable=True))
    op.add_column("financing_applications", sa.Column("life_insurance_fee", sa.Numeric(14, 2), nullable=True))
    op.add_column("financing_applications", sa.Column("excise_duty_pct", sa.Numeric(5, 2), nullable=True))
    op.add_column("financing_applications", sa.Column("excise_duty_amount", sa.Numeric(14, 2), nullable=True))

    op.execute(
        "UPDATE financing_applications SET "
        "concession_applied = (has_existing_logbook_loan AND deposit_percentage = 0), "
        "loan_application_fee_pct = 0, loan_application_fee = 0, "
        "life_insurance_fee_pct = 0, life_insurance_fee = 0, "
        "excise_duty_pct = 0, excise_duty_amount = 0 "
        "WHERE loan_application_fee_pct IS NULL"
    )
    op.alter_column("financing_applications", "concession_applied", nullable=False)
    op.alter_column("financing_applications", "loan_application_fee_pct", nullable=False)
    op.alter_column("financing_applications", "loan_application_fee", nullable=False)
    op.alter_column("financing_applications", "life_insurance_fee_pct", nullable=False)
    op.alter_column("financing_applications", "life_insurance_fee", nullable=False)
    op.alter_column("financing_applications", "excise_duty_pct", nullable=False)
    op.alter_column("financing_applications", "excise_duty_amount", nullable=False)


def downgrade() -> None:
    for col in (
        "excise_duty_amount",
        "excise_duty_pct",
        "life_insurance_fee",
        "life_insurance_fee_pct",
        "loan_application_fee",
        "loan_application_fee_pct",
        "concession_applied",
        "logbook_loan_age_months",
    ):
        op.drop_column("financing_applications", col)
    op.drop_table("financing_settings")