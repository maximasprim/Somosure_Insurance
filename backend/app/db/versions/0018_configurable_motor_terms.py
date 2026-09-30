"""configurable motor terms: comprehensive eligibility action, free
benefits, extension display limits, broker payment plans

Everything added here is nullable / defaulted so every existing rate-card
provider (AMACO, Pioneer Insurance Kenya) and every existing quote/test
keeps pricing exactly as before until an admin explicitly configures the
new fields for a given broker.

Revision ID: 0018
Revises: 0017
Create Date: 2026-09-29
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Reuses the min_sum_insured / max_vehicle_age_years columns that
    # already existed on rate_card_vehicle_classes but were never enforced
    # by the engine - this migration only adds what decides what happens
    # when a vehicle falls outside them.
    op.add_column(
        "rate_card_vehicle_classes",
        sa.Column("comprehensive_ineligible_action", sa.String(20), nullable=False, server_default="downgrade_to_tpo"),
        # downgrade_to_tpo | decline
    )

    # Display-only limit for an existing optional/priced extension (e.g.
    # "Excess protector - up to KES 5,000,000"). Doesn't affect pricing.
    op.add_column("rate_card_extensions", sa.Column("limit_amount", sa.Numeric(14, 2), nullable=True))
    op.add_column("rate_card_extensions", sa.Column("limit_label", sa.String(150), nullable=True))

    # Included ("free") benefits shown alongside a comprehensive quote -
    # windscreen, third party property damage, towing, etc. Unlike
    # rate_card_extensions these are never priced; vehicle_class_id=NULL
    # means "applies to every class for this provider" (same convention
    # as extensions), so leaving it empty for a broker shows nothing new.
    op.create_table(
        "rate_card_free_benefits",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider_id", pg.UUID(as_uuid=True), sa.ForeignKey("insurance_providers.id"), nullable=False),
        sa.Column("vehicle_class_id", pg.UUID(as_uuid=True), sa.ForeignKey("rate_card_vehicle_classes.id"), nullable=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("label", sa.String(150), nullable=False),
        sa.Column("limit_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("limit_label", sa.String(150), nullable=True),
        sa.Column("top_up_note", sa.String(255), nullable=True),
        sa.Column("cover_type", sa.String(20), nullable=False, server_default="comprehensive"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Broker-level payment plan catalog (pay in full / deposit + monthly
    # instalments / straight monthly with a sticker per payment). One JSON
    # column, same "admin edits data, not code" pattern as
    # InsuranceProduct.required_fields - default {} means "no plans
    # configured", which the engine treats identically to today (full
    # payment only).
    op.add_column(
        "insurance_providers",
        sa.Column("payment_plans", sa.JSON(), nullable=False, server_default="{}"),
    )

    # Which configured plan a payment belongs to, and its place in that
    # plan's schedule - all nullable, so a payment made the old way (no
    # plan_code) is unaffected. schedule carries the FULL schedule this
    # leg was priced from (see app/services/motor_terms.py) so the next
    # instalment can be initiated without recomputing it against
    # whatever the rate card looks like by then.
    op.add_column("payments", sa.Column("plan_code", sa.String(30), nullable=True))
    op.add_column("payments", sa.Column("installment_sequence", sa.Integer, nullable=True))
    op.add_column("payments", sa.Column("total_amount", sa.Numeric(14, 2), nullable=True))
    op.add_column("payments", sa.Column("schedule", sa.JSON(), nullable=True))
    op.add_column("payments", sa.Column("root_payment_id", pg.UUID(as_uuid=True), sa.ForeignKey("payments.id"), nullable=True))

    # A sticker's cover window, so a monthly-plan's "one month of cover per
    # payment" can actually be expressed - NULL/NULL (the default, and
    # every sticker before this migration) means "covers the whole policy
    # term", exactly as today.
    op.add_column("stickers", sa.Column("valid_from", sa.Date(), nullable=True))
    op.add_column("stickers", sa.Column("valid_to", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("stickers", "valid_to")
    op.drop_column("stickers", "valid_from")
    op.drop_column("payments", "root_payment_id")
    op.drop_column("payments", "schedule")
    op.drop_column("payments", "total_amount")
    op.drop_column("payments", "installment_sequence")
    op.drop_column("payments", "plan_code")
    op.drop_column("insurance_providers", "payment_plans")
    op.drop_table("rate_card_free_benefits")
    op.drop_column("rate_card_extensions", "limit_label")
    op.drop_column("rate_card_extensions", "limit_amount")
    op.drop_column("rate_card_vehicle_classes", "comprehensive_ineligible_action")
