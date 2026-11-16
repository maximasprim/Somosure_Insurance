"""sales ledger and workbook import

Adds the tables behind the weekly-report import: import_batches, sales_entries, legacy_claims,
ipf_remittances and import_aliases. All new; nothing existing changes. See
app/models/sales_ledger.py for why these sit beside, not inside, policies/applications.

Revision ID: 0032
Revises: 0031
Create Date: 2026-11-11
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def _uuid_pk() -> sa.Column:
    return sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True)


def _stamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]


def _batch_refs() -> list[sa.Column]:
    return [
        sa.Column("first_batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("import_batches.id"), nullable=True),
        sa.Column("last_batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("import_batches.id"), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "import_batches",
        _uuid_pk(),
        sa.Column("kind", sa.String(30), nullable=False, server_default="sales_workbook"),
        sa.Column("filename", sa.String(255)),
        sa.Column("file_sha256", sa.String(64), nullable=False),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="committed"),
        sa.Column("years", sa.JSON()),
        sa.Column("counts", sa.JSON()),
        sa.Column("summary", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_import_batches_file_sha256", "import_batches", ["file_sha256"])

    op.create_table(
        "sales_entries",
        _uuid_pk(),
        sa.Column("natural_key", sa.String(64), nullable=False, unique=True),
        sa.Column("fallback_key", sa.String(64)),
        sa.Column("sheet_name", sa.String(60), nullable=False),
        sa.Column("sheet_year", sa.Integer(), nullable=False),
        sa.Column("sheet_row", sa.Integer()),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("period_month", sa.Integer()),
        sa.Column("client_name", sa.String(200), nullable=False),
        sa.Column("client_key", sa.String(200)),
        sa.Column("phone", sa.String(20)),
        sa.Column("underwriter_raw", sa.String(120)),
        sa.Column("underwriter", sa.String(80)),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("insurance_providers.id"), nullable=True),
        sa.Column("reg_no", sa.String(20)),
        sa.Column("asset_ref", sa.String(120)),
        sa.Column("product_line", sa.String(40), nullable=False, server_default="motor"),
        sa.Column("start_date", sa.Date()),
        sa.Column("expiry_date", sa.Date()),
        sa.Column("date_paid", sa.Date()),
        sa.Column("staff_raw", sa.String(160)),
        sa.Column("staff_name", sa.String(80)),
        sa.Column("branch", sa.String(60)),
        sa.Column("business_type", sa.String(20)),
        sa.Column("policy_number", sa.String(80)),
        sa.Column("cover_type", sa.String(30)),
        sa.Column("premium", sa.Numeric(14, 2)),
        sa.Column("commission", sa.Numeric(14, 2)),
        sa.Column("wht", sa.Numeric(14, 2)),
        sa.Column("net_revenue", sa.Numeric(14, 2)),
        sa.Column("commission_rate", sa.Numeric(7, 4)),
        sa.Column("flags", sa.JSON()),
        sa.Column("issue_level", sa.String(10), nullable=False, server_default="none"),
        sa.Column("raw", sa.JSON()),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("policies.id"), nullable=True),
        *_batch_refs(),
        *_stamps(),
    )
    for column in ("fallback_key", "client_key", "underwriter", "reg_no", "expiry_date", "staff_name", "branch", "policy_number"):
        op.create_index(f"ix_sales_entries_{column}", "sales_entries", [column])
    op.create_index("ix_sales_entries_period", "sales_entries", ["period_year", "period_month"])
    op.create_index("ix_sales_entries_sheet_year", "sales_entries", ["sheet_year"])

    op.create_table(
        "legacy_claims",
        _uuid_pk(),
        sa.Column("natural_key", sa.String(64), nullable=False, unique=True),
        sa.Column("sheet_name", sa.String(60), nullable=False),
        sa.Column("sheet_row", sa.Integer()),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("client_name", sa.String(200), nullable=False),
        sa.Column("client_key", sa.String(200)),
        sa.Column("contact", sa.String(20)),
        sa.Column("reg_or_policy", sa.String(120)),
        sa.Column("reg_no", sa.String(20)),
        sa.Column("underwriter_raw", sa.String(120)),
        sa.Column("underwriter", sa.String(80)),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("insurance_providers.id"), nullable=True),
        sa.Column("date_reported", sa.Date()),
        sa.Column("narrative", sa.Text()),
        sa.Column("outcome_raw", sa.String(120)),
        sa.Column("outcome", sa.String(30), nullable=False, server_default="open"),
        sa.Column("milestones", sa.JSON()),
        sa.Column("sales_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sales_entries.id"), nullable=True),
        sa.Column("flags", sa.JSON()),
        sa.Column("issue_level", sa.String(10), nullable=False, server_default="none"),
        sa.Column("raw", sa.JSON()),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        *_batch_refs(),
        *_stamps(),
    )
    op.create_index("ix_legacy_claims_period_year", "legacy_claims", ["period_year"])
    op.create_index("ix_legacy_claims_client_key", "legacy_claims", ["client_key"])
    op.create_index("ix_legacy_claims_reg_no", "legacy_claims", ["reg_no"])

    op.create_table(
        "ipf_remittances",
        _uuid_pk(),
        sa.Column("natural_key", sa.String(64), nullable=False, unique=True),
        sa.Column("sheet_name", sa.String(60), nullable=False),
        sa.Column("sheet_row", sa.Integer()),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("underwriter_raw", sa.String(120)),
        sa.Column("underwriter", sa.String(80)),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("insurance_providers.id"), nullable=True),
        sa.Column("details", sa.String(255)),
        sa.Column("date_paid", sa.Date()),
        sa.Column("amount", sa.Numeric(14, 2)),
        sa.Column("flags", sa.JSON()),
        sa.Column("issue_level", sa.String(10), nullable=False, server_default="none"),
        sa.Column("raw", sa.JSON()),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        *_batch_refs(),
        *_stamps(),
    )
    op.create_index("ix_ipf_remittances_period_year", "ipf_remittances", ["period_year"])

    op.create_table(
        "import_aliases",
        _uuid_pk(),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("alias_key", sa.String(200), nullable=False),
        sa.Column("as_typed", sa.String(200)),
        sa.Column("canonical", sa.String(120)),
        sa.Column("branch", sa.String(60)),
        sa.Column("confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source", sa.String(20), nullable=False, server_default="auto"),
        *_stamps(),
        sa.UniqueConstraint("kind", "alias_key", name="uq_import_alias_kind_key"),
    )


def downgrade() -> None:
    op.drop_table("import_aliases")
    op.drop_table("ipf_remittances")
    op.drop_table("legacy_claims")
    op.drop_table("sales_entries")
    op.drop_table("import_batches")
