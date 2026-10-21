"""existing-loan max window

Adds one financing setting: the oldest an existing Bidii Credit logbook loan can be and
still be linked to an IPF request (default 10 months - Bidii's longest loan term, so a
loan older than that has finished). The existing concession window (how recent the loan
must be for the deposit, rate and fee waivers) is unchanged and stays the shorter of the
two. Additive; existing rows pick up the default.

Revision ID: 0030
Revises: 0029
Create Date: 2026-10-17
"""

import sqlalchemy as sa
from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "financing_settings",
        sa.Column("existing_loan_max_months", sa.Integer(), nullable=False, server_default="10"),
    )


def downgrade() -> None:
    op.drop_column("financing_settings", "existing_loan_max_months")
