"""comprehensive cover without a valuation report: one-month sticker, valuation pending

Adds four columns to policies, all nullable or defaulted, so existing policies are untouched.

Revision ID: 0038
Revises: 0037
Create Date: 2026-11-18
"""

import sqlalchemy as sa
from alembic import op

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("policies", sa.Column("valuation_pending", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("policies", sa.Column("valuation_due", sa.Date(), nullable=True))
    op.add_column("policies", sa.Column("valuation_received_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("policies", sa.Column("provisional_vehicle", sa.String(30), nullable=True))
    op.create_index("ix_policies_provisional_vehicle", "policies", ["provisional_vehicle"])


def downgrade() -> None:
    op.drop_index("ix_policies_provisional_vehicle", table_name="policies")
    op.drop_column("policies", "provisional_vehicle")
    op.drop_column("policies", "valuation_received_at")
    op.drop_column("policies", "valuation_due")
    op.drop_column("policies", "valuation_pending")
