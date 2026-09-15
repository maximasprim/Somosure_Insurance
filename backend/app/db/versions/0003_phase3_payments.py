"""phase 3 - payments

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-04
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("reference", sa.String(30), nullable=False, unique=True),
        sa.Column("customer_id", pg.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("application_id", pg.UUID(as_uuid=True), sa.ForeignKey("applications.id"), nullable=True),
        sa.Column("policy_id", pg.UUID(as_uuid=True), sa.ForeignKey("policies.id"), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), server_default="KES"),
        sa.Column("method", sa.String(20)),
        sa.Column("status", sa.String(20), server_default="initiated"),
        sa.Column("payer_phone", sa.String(30)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "payment_transactions",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("payment_id", pg.UUID(as_uuid=True), sa.ForeignKey("payments.id"), nullable=False),
        sa.Column("provider", sa.String(30)),
        sa.Column("provider_transaction_id", sa.String(100)),
        sa.Column("direction", sa.String(10)),
        sa.Column("status", sa.String(20)),
        sa.Column("raw_payload", pg.JSON, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_payment_transactions_provider_txn_id", "payment_transactions", ["provider_transaction_id"]
    )


def downgrade() -> None:
    op.drop_table("payment_transactions")
    op.drop_table("payments")
