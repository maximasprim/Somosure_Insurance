"""pricing tiers and anniversary alignment

Two admin-configurable features, both additive (new tables only, nothing existing
is altered):

  * financing_rate_tiers - the Bidii Credit IPF monthly rate by loan amount and tenor.
    With no tiers defined, financing is priced exactly as before;
  * anniversary_settings / short_period_scales / customer_anniversaries - renewing all
    of a customer's covers on one anniversary date, with the short-period premium
    method and tables set by staff.

Revision ID: 0029
Revises: 0028
Create Date: 2026-10-16
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def _uuid_pk():
    return sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True)


def _now(name):
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def upgrade() -> None:
    op.create_table(
        "financing_rate_tiers",
        _uuid_pk(),
        sa.Column("label", sa.String(80), nullable=False),
        sa.Column("applies_to", sa.String(12), nullable=False, server_default="all"),
        sa.Column("min_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("max_amount", sa.Numeric(14, 2)),
        sa.Column("min_term_months", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_term_months", sa.Integer()),
        sa.Column("interest_rate_monthly", sa.Numeric(5, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        _now("created_at"),
        _now("updated_at"),
    )

    op.create_table(
        "anniversary_settings",
        _uuid_pk(),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("method", sa.String(24), nullable=False, server_default="pro_rata_daily"),
        sa.Column("year_basis_days", sa.Integer(), nullable=False, server_default="365"),
        sa.Column("minimum_premium_pct", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("min_stub_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("max_term_days", sa.Integer(), nullable=False, server_default="366"),
        _now("updated_at"),
        sa.Column("updated_by", sa.String(100)),
    )

    op.create_table(
        "short_period_scales",
        _uuid_pk(),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("insurance_providers.id")),
        sa.Column("up_to_days", sa.Integer(), nullable=False),
        sa.Column("percent_of_annual", sa.Numeric(5, 2), nullable=False),
        _now("created_at"),
        _now("updated_at"),
    )
    op.create_index("ix_short_period_scales_provider", "short_period_scales", ["provider_id"])

    op.create_table(
        "customer_anniversaries",
        _uuid_pk(),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("anniversary_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("set_by", sa.String(100)),
        _now("created_at"),
        _now("updated_at"),
        sa.UniqueConstraint("customer_id", name="uq_customer_anniversaries_customer"),
    )


def downgrade() -> None:
    op.drop_table("customer_anniversaries")
    op.drop_index("ix_short_period_scales_provider", table_name="short_period_scales")
    op.drop_table("short_period_scales")
    op.drop_table("anniversary_settings")
    op.drop_table("financing_rate_tiers")
