"""whatsapp integration

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-07
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "whatsapp_conversations",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("phone_number", sa.String(30), nullable=False, unique=True),
        sa.Column("customer_id", pg.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=True),
        sa.Column("state", sa.String(30), server_default="idle"),
        sa.Column("last_message_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("assigned_agent_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "whatsapp_messages",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", pg.UUID(as_uuid=True), sa.ForeignKey("whatsapp_conversations.id"), nullable=False),
        sa.Column("direction", sa.String(10)),
        sa.Column("body", sa.String(4000)),
        sa.Column("provider_message_id", sa.String(100)),
        sa.Column("raw_payload", pg.JSON, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_whatsapp_messages_conversation_id", "whatsapp_messages", ["conversation_id"])


def downgrade() -> None:
    op.drop_table("whatsapp_messages")
    op.drop_table("whatsapp_conversations")
