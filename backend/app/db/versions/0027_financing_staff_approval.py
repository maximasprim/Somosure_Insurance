"""financing staff approval

Adds one switch to the Bidii Credit financing settings: whether a financing
request needs a staff decision. It defaults to on, so a new request waits for
staff instead of being approved the instant the customer applies - financing is
approved separately from the insurance application. Turning it off restores the
previous behaviour (the credit provider's instant answer stands). Existing
applications and agreements are untouched.

Revision ID: 0027
Revises: 0026
Create Date: 2026-10-14
"""

import sqlalchemy as sa
from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "financing_settings",
        sa.Column("require_staff_approval", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("financing_settings", "require_staff_approval")
