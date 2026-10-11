"""partner applications

The queue behind the public "Become a partner" page: businesses ask to become
partners, staff approve or decline with a reason, and approving creates the
partner record. One new table; nothing existing changes.

Revision ID: 0025
Revises: 0024
Create Date: 2026-10-10
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "partner_applications",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("reference", sa.String(30), nullable=False, unique=True),
        sa.Column("business_name", sa.String(200), nullable=False),
        sa.Column("partner_type", sa.String(30), nullable=False),
        sa.Column("contact_name", sa.String(200), nullable=False),
        sa.Column("contact_email", sa.String(255), nullable=False),
        sa.Column("contact_phone", sa.String(30), nullable=False),
        sa.Column("town", sa.String(120), nullable=True),
        sa.Column("website", sa.String(255), nullable=True),
        sa.Column("working_model", sa.String(20), nullable=False),
        sa.Column("monthly_clients", sa.String(10), nullable=False),
        sa.Column("products", sa.JSON(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="pending"),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.String(64), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("partner_id", UUID, sa.ForeignKey("partners.id"), nullable=True),
        sa.Column("customer_id", UUID, sa.ForeignKey("customers.id"), nullable=True),
        sa.Column("affiliate_code", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_partner_applications_contact_email", "partner_applications", ["contact_email"])
    op.create_index("ix_partner_applications_status", "partner_applications", ["status"])


def downgrade() -> None:
    op.drop_index("ix_partner_applications_status", table_name="partner_applications")
    op.drop_index("ix_partner_applications_contact_email", table_name="partner_applications")
    op.drop_table("partner_applications")
