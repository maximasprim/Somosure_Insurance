"""affiliate program

Adds the affiliate program on top of the existing referral feature:
  * affiliate_settings        - one row of admin-editable program settings
  * affiliates                - customers enrolled as affiliates (reusable code)
  * affiliate_rate_rules      - admin-set commission rates (per referrer / product / dates)
  * affiliate_commissions     - what each referrer earned from each policy
  * referrals.referred_at     - when a referral code was actually used (nullable)

Everything is additive: no existing column or row changes, and the program
ships switched OFF with a 0% default rate, so nothing is earned until
management turns it on from the admin dashboard.

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-07
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.add_column("referrals", sa.Column("referred_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "affiliate_settings",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("program_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("default_rate_type", sa.String(10), nullable=False, server_default="percent"),
        sa.Column("default_rate_value", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        sa.Column("min_premium", sa.Numeric(14, 2), nullable=True),
        sa.Column("max_commission_per_policy", sa.Numeric(14, 2), nullable=True),
        sa.Column("scope", sa.String(20), nullable=False, server_default="first_policy"),
        sa.Column("window_months", sa.Integer(), nullable=False, server_default="12"),
        sa.Column("auto_approve", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("allow_self_enrollment", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "affiliates",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("customer_id", UUID, sa.ForeignKey("customers.id"), nullable=False, unique=True),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("status", sa.String(15), nullable=False, server_default="active"),
        sa.Column("payout_method", sa.String(20), nullable=False, server_default="mpesa"),
        sa.Column("payout_phone", sa.String(20), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "affiliate_rate_rules",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("rate_type", sa.String(10), nullable=False, server_default="percent"),
        sa.Column("rate_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("max_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("affiliate_customer_id", UUID, sa.ForeignKey("customers.id"), nullable=True),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("starts_on", sa.Date(), nullable=True),
        sa.Column("ends_on", sa.Date(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "affiliate_commissions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("referral_id", UUID, sa.ForeignKey("referrals.id"), nullable=False),
        sa.Column("referrer_customer_id", UUID, sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("referred_customer_id", UUID, sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("policy_id", UUID, sa.ForeignKey("policies.id"), nullable=True, unique=True),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("premium", sa.Numeric(14, 2), nullable=False),
        sa.Column("rate_type", sa.String(10), nullable=False),
        sa.Column("rate_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("rate_label", sa.String(120), nullable=True),
        sa.Column("commission_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("status", sa.String(15), nullable=False, server_default="pending"),
        sa.Column("status_note", sa.Text(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.String(64), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_by", sa.String(64), nullable=True),
        sa.Column("payout_method", sa.String(20), nullable=True),
        sa.Column("payout_reference", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_affiliate_commissions_referrer_customer_id", "affiliate_commissions", ["referrer_customer_id"])
    op.create_index("ix_affiliate_commissions_status", "affiliate_commissions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_affiliate_commissions_status", table_name="affiliate_commissions")
    op.drop_index("ix_affiliate_commissions_referrer_customer_id", table_name="affiliate_commissions")
    op.drop_table("affiliate_commissions")
    op.drop_table("affiliate_rate_rules")
    op.drop_table("affiliates")
    op.drop_table("affiliate_settings")
    op.drop_column("referrals", "referred_at")
