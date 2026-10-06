"""optional company-applicant financing terms

Adds two NULLABLE columns to financing_settings so management can give
company applicants their own deposit percentage and/or monthly interest rate.
NULL (the default for the existing row) means "same as the standard terms",
so applying this migration changes no behaviour until someone sets a value
from the admin financing settings screen.

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-05
"""

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("financing_settings", sa.Column("corporate_deposit_percentage", sa.Numeric(5, 2), nullable=True))
    op.add_column("financing_settings", sa.Column("corporate_interest_rate_monthly", sa.Numeric(5, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("financing_settings", "corporate_interest_rate_monthly")
    op.drop_column("financing_settings", "corporate_deposit_percentage")
