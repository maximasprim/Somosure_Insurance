"""phase 7 - aggregator multi-insurer quotes

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-05
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("quotes", sa.Column("underlying_provider_name", sa.String(150), nullable=True))


def downgrade() -> None:
    op.drop_column("quotes", "underlying_provider_name")
