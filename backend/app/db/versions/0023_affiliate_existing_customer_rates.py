"""affiliate: a different rate for existing customers

Adds three NULLABLE columns, so nothing changes until management sets a value:
  * affiliate_settings.existing_customer_rate_type / _value - the rate paid when
    the person referring already has an active policy with us;
  * affiliate_rate_rules.referrer_segment - lets a special rate apply only to
    referrers who are (or aren't) existing customers.

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-08
"""

import sqlalchemy as sa
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("affiliate_settings", sa.Column("existing_customer_rate_type", sa.String(10), nullable=True))
    op.add_column("affiliate_settings", sa.Column("existing_customer_rate_value", sa.Numeric(12, 2), nullable=True))
    op.add_column("affiliate_rate_rules", sa.Column("referrer_segment", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("affiliate_rate_rules", "referrer_segment")
    op.drop_column("affiliate_settings", "existing_customer_rate_value")
    op.drop_column("affiliate_settings", "existing_customer_rate_type")
