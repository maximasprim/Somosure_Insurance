"""link the sales ledger to customers, and keep renewal follow-up

Adds sales_entries.customer_id and follow_up_* columns, and legacy_claims.customer_id. All nullable;
nothing existing changes.

Revision ID: 0034
Revises: 0033
Create Date: 2026-11-12
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sales_entries", sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=True))
    op.add_column("sales_entries", sa.Column("follow_up_status", sa.String(20), nullable=True))
    op.add_column("sales_entries", sa.Column("follow_up_note", sa.Text(), nullable=True))
    op.add_column("sales_entries", sa.Column("follow_up_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sales_entries", sa.Column("follow_up_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True))
    op.create_index("ix_sales_entries_customer_id", "sales_entries", ["customer_id"])
    op.add_column("legacy_claims", sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=True))
    op.create_index("ix_legacy_claims_customer_id", "legacy_claims", ["customer_id"])


def downgrade() -> None:
    op.drop_index("ix_legacy_claims_customer_id", table_name="legacy_claims")
    op.drop_column("legacy_claims", "customer_id")
    op.drop_index("ix_sales_entries_customer_id", table_name="sales_entries")
    for column in ("follow_up_by", "follow_up_at", "follow_up_note", "follow_up_status", "customer_id"):
        op.drop_column("sales_entries", column)
