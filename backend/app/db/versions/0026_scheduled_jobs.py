"""scheduled jobs

Bookkeeping for the background scheduler (renewal reminders, abandoned-quote
recovery, due automations, M-Pesa reconciliation): one row per job holding when it
runs next, a lease so only one server instance runs it, and its last result. One
new table; nothing existing changes.

Revision ID: 0026
Revises: 0025
Create Date: 2026-10-12
"""

import sqlalchemy as sa
from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scheduled_jobs",
        sa.Column("name", sa.String(60), primary_key=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(20), nullable=True),
        sa.Column("last_result", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("scheduled_jobs")
