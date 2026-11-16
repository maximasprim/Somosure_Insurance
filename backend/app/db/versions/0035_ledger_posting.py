"""post workbook rows into the system's own tables

Adds, to the sales ledger, the ids of the records created for a posted row, and a table linking the
underwriters named in the sheet to providers. Core tables (customers, quotes, applications, policies,
payments) are not changed.

Revision ID: 0035
Revises: 0034
Create Date: 2026-11-12
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    for column, target in (
        ("quote_request_id", "quote_requests.id"),
        ("quote_id", "quotes.id"),
        ("application_id", "applications.id"),
        ("payment_id", "payments.id"),
    ):
        op.add_column("sales_entries", sa.Column(column, UUID, sa.ForeignKey(target), nullable=True))
    op.add_column("sales_entries", sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sales_entries", sa.Column("post_flags", sa.JSON(), nullable=True))
    op.create_index("ix_sales_entries_posted_at", "sales_entries", ["posted_at"])
    op.create_table(
        "underwriter_links",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("underwriter", sa.String(80), nullable=False, unique=True),
        sa.Column("provider_id", UUID, sa.ForeignKey("insurance_providers.id"), nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="auto"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("underwriter_links")
    op.drop_index("ix_sales_entries_posted_at", table_name="sales_entries")
    for column in ("post_flags", "posted_at", "payment_id", "application_id", "quote_id", "quote_request_id"):
        op.drop_column("sales_entries", column)
