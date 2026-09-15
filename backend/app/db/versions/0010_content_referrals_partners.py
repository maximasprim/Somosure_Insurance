"""content cms, referrals, partners

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-06
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "content_categories",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(100)),
    )

    op.create_table(
        "content",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(150), nullable=False, unique=True),
        sa.Column("title", sa.String(255)),
        sa.Column("body", sa.String(20000)),
        sa.Column("category_id", pg.UUID(as_uuid=True), sa.ForeignKey("content_categories.id"), nullable=True),
        sa.Column("is_published", sa.Boolean, server_default=sa.false()),
        sa.Column("author_user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "faqs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("question", sa.String(500)),
        sa.Column("answer", sa.String(5000)),
        sa.Column("category_id", pg.UUID(as_uuid=True), sa.ForeignKey("content_categories.id"), nullable=True),
        sa.Column("display_order", sa.Integer, server_default="0"),
        sa.Column("is_published", sa.Boolean, server_default=sa.true()),
    )

    op.create_table(
        "referrals",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("referrer_customer_id", pg.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("referred_customer_id", pg.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=True),
        sa.Column("policy_id", pg.UUID(as_uuid=True), sa.ForeignKey("policies.id"), nullable=True),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("reward_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("reward_paid", sa.Boolean, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "partners",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200)),
        sa.Column("partner_type", sa.String(30)),
        sa.Column("contact_name", sa.String(200)),
        sa.Column("contact_email", sa.String(255)),
        sa.Column("contact_phone", sa.String(30)),
        sa.Column("is_active", sa.Boolean, server_default=sa.true()),
        sa.Column("managed_by_user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("partners")
    op.drop_table("referrals")
    op.drop_table("faqs")
    op.drop_table("content")
    op.drop_table("content_categories")
