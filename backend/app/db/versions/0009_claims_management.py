"""claims management

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-06
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "claims",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("reference", sa.String(30), nullable=False, unique=True),
        sa.Column("policy_id", pg.UUID(as_uuid=True), sa.ForeignKey("policies.id"), nullable=False),
        sa.Column("customer_id", pg.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("incident_date", sa.Date),
        sa.Column("incident_description", sa.String(2000)),
        sa.Column("incident_location", sa.String(255)),
        sa.Column("status", sa.String(30), server_default="reported"),
        sa.Column("provider_reference", sa.String(100)),
        sa.Column("provider_metadata", pg.JSON, server_default="{}"),
        sa.Column("assigned_to_user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_claims_customer_id", "claims", ["customer_id"])
    op.create_index("ix_claims_policy_id", "claims", ["policy_id"])

    op.create_table(
        "claim_documents",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("claim_id", pg.UUID(as_uuid=True), sa.ForeignKey("claims.id"), nullable=False),
        sa.Column("document_type", sa.String(50)),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "claim_events",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("claim_id", pg.UUID(as_uuid=True), sa.ForeignKey("claims.id"), nullable=False),
        sa.Column("event_type", sa.String(30)),
        sa.Column("from_status", sa.String(30)),
        sa.Column("to_status", sa.String(30)),
        sa.Column("notes", sa.String(2000)),
        sa.Column("actor_user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("claim_events")
    op.drop_table("claim_documents")
    op.drop_table("claims")
