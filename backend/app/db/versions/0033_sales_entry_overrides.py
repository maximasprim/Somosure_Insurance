"""accepted date fixes on sales ledger rows

Adds sales_entries.overrides: the suggested date fixes a person accepted, kept until the sheet
itself is corrected. One nullable column; nothing existing changes.

Revision ID: 0033
Revises: 0032
Create Date: 2026-11-11
"""

import sqlalchemy as sa
from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sales_entries", sa.Column("overrides", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("sales_entries", "overrides")
