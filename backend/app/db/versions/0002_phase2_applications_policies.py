"""phase 2 - applications, policies, vehicles

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-04
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vehicles",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", pg.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("registration_number", sa.String(20)),
        sa.Column("chassis_number", sa.String(50)),
        sa.Column("engine_number", sa.String(50)),
        sa.Column("make", sa.String(80)),
        sa.Column("model", sa.String(80)),
        sa.Column("year", sa.Integer),
        sa.Column("value", sa.Numeric(14, 2)),
        sa.Column("usage", sa.String(30)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_vehicles_registration_number", "vehicles", ["registration_number"])

    op.create_table(
        "insured_assets",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", pg.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("category", sa.String(30)),
        sa.Column("description", sa.String(500)),
        sa.Column("value", sa.Numeric(14, 2)),
        sa.Column("details", pg.JSON, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "applications",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("reference", sa.String(30), nullable=False, unique=True),
        sa.Column("quote_id", pg.UUID(as_uuid=True), sa.ForeignKey("quotes.id"), nullable=False),
        sa.Column("customer_id", pg.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("vehicle_id", pg.UUID(as_uuid=True), sa.ForeignKey("vehicles.id"), nullable=True),
        sa.Column("insured_asset_id", pg.UUID(as_uuid=True), sa.ForeignKey("insured_assets.id"), nullable=True),
        sa.Column("applicant_details", pg.JSON, server_default="{}"),
        sa.Column("status", sa.String(30), server_default="draft"),
        sa.Column("provider_reference", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "application_documents",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("application_id", pg.UUID(as_uuid=True), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("document_type", sa.String(50)),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), server_default="uploaded"),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "policies",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("policy_number", sa.String(50), nullable=False, unique=True),
        sa.Column("application_id", pg.UUID(as_uuid=True), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("provider_id", pg.UUID(as_uuid=True), sa.ForeignKey("insurance_providers.id"), nullable=False),
        sa.Column("product_id", pg.UUID(as_uuid=True), sa.ForeignKey("insurance_products.id"), nullable=True),
        sa.Column("customer_id", pg.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("start_date", sa.Date),
        sa.Column("end_date", sa.Date),
        sa.Column("premium", sa.Numeric(14, 2)),
        sa.Column("payment_status", sa.String(20), server_default="pending"),
        sa.Column("status", sa.String(30), server_default="active"),
        sa.Column("agent_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("source", sa.String(50)),
        sa.Column("commission", sa.Numeric(14, 2)),
        sa.Column("is_mock", sa.Boolean, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "policy_documents",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("policy_id", pg.UUID(as_uuid=True), sa.ForeignKey("policies.id"), nullable=False),
        sa.Column("document_type", sa.String(50)),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("is_mock", sa.Boolean, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "policy_events",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("policy_id", pg.UUID(as_uuid=True), sa.ForeignKey("policies.id"), nullable=False),
        sa.Column("event_type", sa.String(50)),
        sa.Column("from_status", sa.String(30)),
        sa.Column("to_status", sa.String(30)),
        sa.Column("metadata_json", pg.JSON, server_default="{}"),
        sa.Column("actor_user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    for table in [
        "policy_events",
        "policy_documents",
        "policies",
        "application_documents",
        "applications",
        "insured_assets",
        "vehicles",
    ]:
        op.drop_table(table)
