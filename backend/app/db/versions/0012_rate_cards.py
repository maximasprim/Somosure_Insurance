"""configurable rate cards

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-19
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rate_card_vehicle_classes",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider_id", pg.UUID(as_uuid=True), sa.ForeignKey("insurance_providers.id"), nullable=False),
        sa.Column("product_category", sa.String(30), server_default="motor"),
        sa.Column("code", sa.String(60), nullable=False),
        sa.Column("label", sa.String(150)),
        sa.Column("min_sum_insured", sa.Numeric(14, 2), nullable=True),
        sa.Column("max_vehicle_age_years", sa.Integer(), nullable=True),
        sa.Column("source_document", sa.String(255), nullable=True),
        sa.Column("data_confidence", sa.String(20), server_default="verified"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("provider_id", "code", name="uq_rate_card_class_provider_code"),
    )
    op.create_index("ix_rate_card_classes_provider_id", "rate_card_vehicle_classes", ["provider_id"])

    op.create_table(
        "rate_card_tiers",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "vehicle_class_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("rate_card_vehicle_classes.id"),
            nullable=False,
        ),
        sa.Column("cover_type", sa.String(20)),
        sa.Column("band_unit", sa.String(20), server_default="sum_insured"),
        sa.Column("subtype_key", sa.String(50), nullable=True),
        sa.Column("min_value", sa.Numeric(14, 2), nullable=True),
        sa.Column("max_value", sa.Numeric(14, 2), nullable=True),
        sa.Column("rate_percent", sa.Numeric(6, 3), nullable=True),
        sa.Column("flat_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("min_premium", sa.Numeric(14, 2), nullable=True),
        sa.Column("label", sa.String(150), nullable=True),
        sa.Column("tier_order", sa.Integer(), server_default="0"),
    )
    op.create_index("ix_rate_card_tiers_vehicle_class_id", "rate_card_tiers", ["vehicle_class_id"])

    op.create_table(
        "rate_card_extensions",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider_id", pg.UUID(as_uuid=True), sa.ForeignKey("insurance_providers.id"), nullable=False),
        sa.Column(
            "vehicle_class_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("rate_card_vehicle_classes.id"),
            nullable=True,
        ),
        sa.Column("code", sa.String(50)),
        sa.Column("label", sa.String(150)),
        sa.Column("basis", sa.String(20), server_default="percent_of_sum_insured"),
        sa.Column("rate_percent", sa.Numeric(6, 3), nullable=True),
        sa.Column("flat_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("min_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_rate_card_extensions_provider_id", "rate_card_extensions", ["provider_id"])

    op.create_table(
        "rate_card_excesses",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider_id", pg.UUID(as_uuid=True), sa.ForeignKey("insurance_providers.id"), nullable=False),
        sa.Column(
            "vehicle_class_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("rate_card_vehicle_classes.id"),
            nullable=False,
        ),
        sa.Column("peril", sa.String(50)),
        sa.Column("basis", sa.String(20), server_default="percent_of_sum_insured"),
        sa.Column("rate_percent", sa.Numeric(6, 3), nullable=True),
        sa.Column("flat_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("min_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("label", sa.String(150), nullable=True),
    )
    op.create_index("ix_rate_card_excesses_vehicle_class_id", "rate_card_excesses", ["vehicle_class_id"])


def downgrade() -> None:
    op.drop_table("rate_card_excesses")
    op.drop_table("rate_card_extensions")
    op.drop_table("rate_card_tiers")
    op.drop_table("rate_card_vehicle_classes")
