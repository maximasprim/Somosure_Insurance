"""automatic Google Sheet import and import version history

Adds sales_import_settings (one row), import_versions (every committed import, with the stored workbook file) and
sales_import_runs (every automatic attempt). Only new tables - nothing existing is altered.

Revision ID: 0037
Revises: 0036
Create Date: 2026-11-17
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sales_import_settings",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("sheet_url", sa.Text),
        sa.Column("sheet_id", sa.String(120)),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("frequency", sa.String(10), nullable=False, server_default="weekly"),
        sa.Column("weekday", sa.Integer, nullable=False, server_default="0"),
        sa.Column("day_of_month", sa.Integer, nullable=False, server_default="1"),
        sa.Column("hour", sa.Integer, nullable=False, server_default="6"),
        sa.Column("period_from", sa.String(7)),
        sa.Column("period_to", sa.String(7)),
        sa.Column("auto_post", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("paused_reason", sa.Text),
        sa.Column("next_run_at", sa.DateTime(timezone=True)),
        sa.Column("last_run_at", sa.DateTime(timezone=True)),
        sa.Column("last_status", sa.String(20)),
        sa.Column("last_message", sa.Text),
        sa.Column("consecutive_failures", sa.Integer, nullable=False, server_default="0"),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_sales_import_settings_singleton"),
    )
    op.create_table(
        "import_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("version_no", sa.Integer, nullable=False, unique=True),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("import_batches.id"), nullable=True),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("filename", sa.String(255)),
        sa.Column("file_sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("period_from", sa.String(7)),
        sa.Column("period_to", sa.String(7)),
        sa.Column("counts", sa.JSON),
        sa.Column("note", sa.Text),
        sa.Column("reverted_to_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("import_versions.id"), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_import_versions_batch_id", "import_versions", ["batch_id"])
    op.create_index("ix_import_versions_file_sha256", "import_versions", ["file_sha256"])
    op.create_table(
        "sales_import_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("trigger", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("message", sa.Text),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("import_versions.id"), nullable=True),
        sa.Column("counts", sa.JSON),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("sales_import_runs")
    op.drop_index("ix_import_versions_file_sha256", table_name="import_versions")
    op.drop_index("ix_import_versions_batch_id", table_name="import_versions")
    op.drop_table("import_versions")
    op.drop_table("sales_import_settings")
