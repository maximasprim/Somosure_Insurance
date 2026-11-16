"""sales recorded directly in the system

Adds sales_entries.origin ('workbook' for imports, 'manual' for sales typed into the system) and entered_by.

Revision ID: 0036
Revises: 0035
Create Date: 2026-11-13
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sales_entries", sa.Column("origin", sa.String(20), nullable=False, server_default="workbook"))
    op.add_column("sales_entries", sa.Column("entered_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True))


def downgrade() -> None:
    op.drop_column("sales_entries", "entered_by")
    op.drop_column("sales_entries", "origin")
