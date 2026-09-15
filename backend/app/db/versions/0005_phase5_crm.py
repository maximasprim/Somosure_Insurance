"""phase 5 - crm (leads, activities, communications, tasks)

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-04
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "leads",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", pg.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("stage", sa.String(20), server_default="new"),
        sa.Column("source", sa.String(20), server_default="website"),
        sa.Column("product_interest", sa.String(30)),
        sa.Column("assigned_agent_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("quote_request_id", pg.UUID(as_uuid=True), sa.ForeignKey("quote_requests.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_leads_customer_id", "leads", ["customer_id"])
    op.create_index("ix_leads_stage", "leads", ["stage"])

    op.create_table(
        "lead_activities",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("lead_id", pg.UUID(as_uuid=True), sa.ForeignKey("leads.id"), nullable=False),
        sa.Column("activity_type", sa.String(30)),
        sa.Column("notes", sa.String(2000)),
        sa.Column("actor_user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "communications",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", pg.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("channel", sa.String(20)),
        sa.Column("direction", sa.String(10)),
        sa.Column("subject", sa.String(255)),
        sa.Column("body", sa.String(4000)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "tasks",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(255)),
        sa.Column("lead_id", pg.UUID(as_uuid=True), sa.ForeignKey("leads.id"), nullable=True),
        sa.Column("assigned_to_user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("tasks")
    op.drop_table("communications")
    op.drop_table("lead_activities")
    op.drop_table("leads")
