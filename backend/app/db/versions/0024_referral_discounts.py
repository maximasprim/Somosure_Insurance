"""referral discounts for existing customers

Lets an existing customer who refers someone that buys insurance be rewarded
with a DISCOUNT CREDIT on their own insurance (instead of, or as well as,
commission). Staff apply each credit to one of the customer's applications.

  * affiliate_settings: existing_customer_reward ("commission" by default, so
    nothing changes), plus the credit's type / value / ceiling / validity
  * referral_discounts: the credits
  * applications: discount_amount / discount_credit_id / discount_note

Everything is additive and defaults to "no discount".

Revision ID: 0024
Revises: 0023
Create Date: 2026-10-08
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.add_column("affiliate_settings", sa.Column("existing_customer_reward", sa.String(12), nullable=False, server_default="commission"))
    op.add_column("affiliate_settings", sa.Column("discount_type", sa.String(10), nullable=False, server_default="percent"))
    op.add_column("affiliate_settings", sa.Column("discount_value", sa.Numeric(12, 2), nullable=False, server_default="0.00"))
    op.add_column("affiliate_settings", sa.Column("discount_max_amount", sa.Numeric(14, 2), nullable=True))
    op.add_column("affiliate_settings", sa.Column("discount_valid_days", sa.Integer(), nullable=False, server_default="365"))

    op.add_column("applications", sa.Column("discount_amount", sa.Numeric(14, 2), nullable=True))
    op.add_column("applications", sa.Column("discount_credit_id", UUID, nullable=True))
    op.add_column("applications", sa.Column("discount_note", sa.String(255), nullable=True))

    op.create_table(
        "referral_discounts",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("customer_id", UUID, sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("referral_id", UUID, sa.ForeignKey("referrals.id"), nullable=True),
        sa.Column("source", sa.String(10), nullable=False, server_default="referral"),
        sa.Column("source_policy_id", UUID, nullable=True, unique=True),
        sa.Column("discount_type", sa.String(10), nullable=False, server_default="percent"),
        sa.Column("discount_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("max_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(12), nullable=False, server_default="available"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status_note", sa.Text(), nullable=True),
        sa.Column("applied_application_id", UUID, nullable=True),
        sa.Column("applied_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_by", sa.String(64), nullable=True),
        sa.Column("created_by", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_referral_discounts_customer_id", "referral_discounts", ["customer_id"])
    op.create_index("ix_referral_discounts_status", "referral_discounts", ["status"])


def downgrade() -> None:
    op.drop_index("ix_referral_discounts_status", table_name="referral_discounts")
    op.drop_index("ix_referral_discounts_customer_id", table_name="referral_discounts")
    op.drop_table("referral_discounts")
    op.drop_column("applications", "discount_note")
    op.drop_column("applications", "discount_credit_id")
    op.drop_column("applications", "discount_amount")
    for col in ("discount_valid_days", "discount_max_amount", "discount_value", "discount_type", "existing_customer_reward"):
        op.drop_column("affiliate_settings", col)
