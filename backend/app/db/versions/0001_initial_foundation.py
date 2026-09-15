"""initial foundation schema

Revision ID: 0001
Revises:
Create Date: 2026-09-03
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    op.create_table(
        "roles",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(50), nullable=False, unique=True),
        sa.Column("description", sa.String(255)),
    )

    op.create_table(
        "permissions",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.String(255)),
    )

    op.create_table(
        "role_permissions",
        sa.Column("role_id", pg.UUID(as_uuid=True), sa.ForeignKey("roles.id"), primary_key=True),
        sa.Column("permission_id", pg.UUID(as_uuid=True), sa.ForeignKey("permissions.id"), primary_key=True),
    )

    op.create_table(
        "users",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("phone", sa.String(30)),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, server_default=sa.true()),
        sa.Column("is_verified", sa.Boolean, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "user_roles",
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("role_id", pg.UUID(as_uuid=True), sa.ForeignKey("roles.id"), primary_key=True),
    )

    op.create_table(
        "customers",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255)),
        sa.Column("phone", sa.String(30), nullable=False),
        sa.Column("id_number", sa.String(50)),
        sa.Column("kra_pin", sa.String(30)),
        sa.Column("lead_source", sa.String(50)),
        sa.Column("consent_marketing", sa.Boolean, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_customers_email", "customers", ["email"])
    op.create_index("ix_customers_phone", "customers", ["phone"])

    op.create_table(
        "customer_contacts",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", pg.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("label", sa.String(50)),
        sa.Column("full_name", sa.String(255)),
        sa.Column("phone", sa.String(30)),
        sa.Column("email", sa.String(255)),
    )

    op.create_table(
        "insurance_providers",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("provider_type", sa.String(30)),
        sa.Column("logo_url", sa.String(500)),
        sa.Column("integration_mode", sa.String(20), server_default="mock"),
        sa.Column("api_base_url", sa.String(500)),
        sa.Column("credentials_secret_ref", sa.String(255)),
        sa.Column("supports_quote", sa.Boolean, server_default=sa.false()),
        sa.Column("supports_policy", sa.Boolean, server_default=sa.false()),
        sa.Column("supports_payment", sa.Boolean, server_default=sa.false()),
        sa.Column("supports_documents", sa.Boolean, server_default=sa.false()),
        sa.Column("supports_claims", sa.Boolean, server_default=sa.false()),
        sa.Column("supports_renewal", sa.Boolean, server_default=sa.false()),
        sa.Column("supports_webhooks", sa.Boolean, server_default=sa.false()),
        sa.Column("status", sa.String(20), server_default="inactive"),
        sa.Column("integration_version", sa.String(20)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "insurance_products",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider_id", pg.UUID(as_uuid=True), sa.ForeignKey("insurance_providers.id")),
        sa.Column("category", sa.String(30)),
        sa.Column("subtype", sa.String(50)),
        sa.Column("name", sa.String(150)),
        sa.Column("description", sa.String(1000)),
        sa.Column("is_active", sa.Boolean, server_default=sa.true()),
        sa.Column("required_fields", pg.JSON, server_default="{}"),
        sa.Column("required_documents", pg.JSON, server_default="{}"),
    )

    op.create_table(
        "insurance_product_plans",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("product_id", pg.UUID(as_uuid=True), sa.ForeignKey("insurance_products.id")),
        sa.Column("name", sa.String(150)),
        sa.Column("coverage_summary", pg.JSON, server_default="{}"),
    )

    op.create_table(
        "quote_requests",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("reference", sa.String(30), nullable=False, unique=True),
        sa.Column("customer_id", pg.UUID(as_uuid=True), sa.ForeignKey("customers.id")),
        sa.Column("category", sa.String(30)),
        sa.Column("input_data", pg.JSON, server_default="{}"),
        sa.Column("status", sa.String(30), server_default="collecting"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "quotes",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("quote_request_id", pg.UUID(as_uuid=True), sa.ForeignKey("quote_requests.id")),
        sa.Column("provider_id", pg.UUID(as_uuid=True), sa.ForeignKey("insurance_providers.id")),
        sa.Column("product_id", pg.UUID(as_uuid=True), sa.ForeignKey("insurance_products.id"), nullable=True),
        sa.Column("premium", sa.Numeric(14, 2)),
        sa.Column("taxes", sa.Numeric(14, 2), server_default="0"),
        sa.Column("fees", sa.Numeric(14, 2), server_default="0"),
        sa.Column("total", sa.Numeric(14, 2)),
        sa.Column("currency", sa.String(3), server_default="KES"),
        sa.Column("coverage", pg.JSON, server_default="{}"),
        sa.Column("exclusions", pg.JSON, server_default="{}"),
        sa.Column("deductibles", pg.JSON, server_default="{}"),
        sa.Column("payment_options", pg.JSON, server_default="{}"),
        sa.Column("provider_metadata", pg.JSON, server_default="{}"),
        sa.Column("is_mock", sa.Boolean, server_default=sa.true()),
        sa.Column("valid_until", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), server_default="available"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "quote_items",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("quote_id", pg.UUID(as_uuid=True), sa.ForeignKey("quotes.id")),
        sa.Column("label", sa.String(150)),
        sa.Column("amount", sa.Numeric(14, 2)),
    )


def downgrade() -> None:
    for table in [
        "quote_items",
        "quotes",
        "quote_requests",
        "insurance_product_plans",
        "insurance_products",
        "insurance_providers",
        "customer_contacts",
        "customers",
        "user_roles",
        "users",
        "role_permissions",
        "permissions",
        "roles",
    ]:
        op.drop_table(table)
