"""phase 6 - automation (notifications, renewals, stickers, rules)

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-04
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("customer_id", pg.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("channel", sa.String(20)),
        sa.Column("event_type", sa.String(50)),
        sa.Column("subject", sa.String(255)),
        sa.Column("body", sa.String(2000)),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("is_read", sa.Boolean, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_notifications_customer_id", "notifications", ["customer_id"])

    op.create_table(
        "renewals",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("policy_id", pg.UUID(as_uuid=True), sa.ForeignKey("policies.id"), nullable=False, unique=True),
        sa.Column("due_date", sa.Date),
        sa.Column("status", sa.String(20), server_default="due"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "renewal_events",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("renewal_id", pg.UUID(as_uuid=True), sa.ForeignKey("renewals.id"), nullable=False),
        sa.Column("event_type", sa.String(30)),
        sa.Column("days_before_expiry", sa.Integer),
        sa.Column("notes", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "stickers",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("reference", sa.String(30), nullable=False, unique=True),
        sa.Column("policy_id", pg.UUID(as_uuid=True), sa.ForeignKey("policies.id"), nullable=False),
        sa.Column("status", sa.String(30), server_default="pending"),
        sa.Column("qr_payload", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "sticker_events",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("sticker_id", pg.UUID(as_uuid=True), sa.ForeignKey("stickers.id"), nullable=False),
        sa.Column("from_status", sa.String(30)),
        sa.Column("to_status", sa.String(30)),
        sa.Column("actor_user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("notes", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "automation_rules",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(150)),
        sa.Column("trigger_event", sa.String(50)),
        sa.Column("conditions", pg.JSON, server_default="{}"),
        sa.Column("action_type", sa.String(50)),
        sa.Column("action_config", pg.JSON, server_default="{}"),
        sa.Column("delay_seconds", sa.Integer, server_default="0"),
        sa.Column("is_active", sa.Boolean, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "automation_runs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("rule_id", pg.UUID(as_uuid=True), sa.ForeignKey("automation_rules.id"), nullable=False),
        sa.Column("trigger_event", sa.String(50)),
        sa.Column("entity_type", sa.String(30)),
        sa.Column("entity_id", sa.String(50)),
        sa.Column("context", pg.JSON, server_default="{}"),
        sa.Column("status", sa.String(20), server_default="scheduled"),
        sa.Column("scheduled_for", sa.DateTime(timezone=True)),
        sa.Column("executed_at", sa.DateTime(timezone=True)),
        sa.Column("result", pg.JSON, server_default="{}"),
        sa.Column("error", sa.String(1000)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_automation_runs_status", "automation_runs", ["status"])


def downgrade() -> None:
    op.drop_table("automation_runs")
    op.drop_table("automation_rules")
    op.drop_table("sticker_events")
    op.drop_table("stickers")
    op.drop_table("renewal_events")
    op.drop_table("renewals")
    op.drop_table("notifications")
