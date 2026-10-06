"""audit trail

Creates the append-only audit_logs table: who did what, to which record, when
and why. Database triggers refuse any UPDATE, DELETE or TRUNCATE on it, so even
application code (or a careless query) cannot rewrite history. There are no
foreign keys, so the trail outlives any user or customer record.

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-05
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("seq", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("actor_type", sa.String(10), nullable=False),
        sa.Column("actor_user_id", sa.String(64), nullable=True),
        sa.Column("actor_name", sa.String(255), nullable=True),
        sa.Column("actor_email", sa.String(255), nullable=True),
        sa.Column("actor_role", sa.String(50), nullable=True),
        sa.Column("entity_type", sa.String(60), nullable=True),
        sa.Column("entity_id", sa.String(64), nullable=True),
        sa.Column("entity_label", sa.String(255), nullable=True),
        sa.Column("related_customer_id", sa.String(64), nullable=True),
        sa.Column("summary", sa.String(500), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("changes", sa.JSON(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("request_id", sa.String(36), nullable=True),
        sa.Column("method", sa.String(10), nullable=True),
        sa.Column("path", sa.String(500), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(300), nullable=True),
    )
    op.create_index("ix_audit_logs_seq", "audit_logs", ["seq"])
    op.create_index("ix_audit_logs_occurred_at", "audit_logs", ["occurred_at"])
    op.create_index("ix_audit_logs_kind", "audit_logs", ["kind"])
    op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"])
    op.create_index("ix_audit_logs_related_customer_id", "audit_logs", ["related_customer_id"])
    op.create_index("ix_audit_logs_request_id", "audit_logs", ["request_id"])
    op.create_index("ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"])

    # Append-only: refuse changes and removal at the database level.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_logs_append_only() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs is append-only: % is not allowed', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        "CREATE TRIGGER audit_logs_no_change BEFORE UPDATE OR DELETE ON audit_logs "
        "FOR EACH ROW EXECUTE FUNCTION audit_logs_append_only();"
    )
    op.execute(
        "CREATE TRIGGER audit_logs_no_truncate BEFORE TRUNCATE ON audit_logs "
        "FOR EACH STATEMENT EXECUTE FUNCTION audit_logs_append_only();"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_logs_no_truncate ON audit_logs;")
    op.execute("DROP TRIGGER IF EXISTS audit_logs_no_change ON audit_logs;")
    op.execute("DROP FUNCTION IF EXISTS audit_logs_append_only();")
    op.drop_table("audit_logs")
