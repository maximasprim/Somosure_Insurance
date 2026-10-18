"""ipf gaps: loan officers, cheques, early settlement, linked/unlinked, tracker

Closes the gaps between the Bidii Credit IPF product deck and the system:

  * loan_officers + loan_officer_commissions - who brought an IPF sale in and the
    share of Somosure's net commission they earn (default 10%), plus a monthly target;
  * financing_cheques - the post-dated cheques held to cover the repayments;
  * financing_settlements - a loan cleared before its agreed term (default fee 3.5%);
  * financing_applications: ipf_type (linked/unlinked), loan officer, vehicle tracker,
    and when the original logbook was handed in;
  * financing_settings: the early-settlement fee %, the officer commission %, and an
    optional "Somosure commission as % of premium";
  * the deck's minimum term is 3 months: the minimum moves from 4 to 3, but only where
    it is still the old default - a value staff set themselves is left alone.

Everything is additive; existing rows keep working unchanged.

Revision ID: 0028
Revises: 0027
Create Date: 2026-10-15
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def _uuid_pk():
    return sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True)


def _now(name):
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def upgrade() -> None:
    # --- settings
    op.add_column("financing_settings", sa.Column("early_settlement_fee_pct", sa.Numeric(5, 2), nullable=False, server_default="3.50"))
    op.add_column("financing_settings", sa.Column("loan_officer_commission_pct", sa.Numeric(5, 2), nullable=False, server_default="10.00"))
    op.add_column("financing_settings", sa.Column("somosure_commission_pct_of_premium", sa.Numeric(5, 2), nullable=True))
    op.execute("UPDATE financing_settings SET min_term_months = 3 WHERE min_term_months = 4")

    # --- loan officers
    op.create_table(
        "loan_officers",
        _uuid_pk(),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("staff_number", sa.String(40), nullable=False),
        sa.Column("email", sa.String(255)),
        sa.Column("phone", sa.String(30)),
        sa.Column("monthly_target", sa.Numeric(14, 2)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        _now("created_at"),
        _now("updated_at"),
        sa.UniqueConstraint("staff_number", name="uq_loan_officers_staff_number"),
    )
    op.create_index("ix_loan_officers_staff_number", "loan_officers", ["staff_number"])

    # --- the financing application's own new columns (after loan_officers exists for the FK)
    op.add_column("financing_applications", sa.Column("ipf_type", sa.String(10), nullable=False, server_default="unlinked"))
    op.add_column("financing_applications", sa.Column("loan_officer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("loan_officers.id")))
    op.add_column("financing_applications", sa.Column("tracker_provider", sa.String(80)))
    op.add_column("financing_applications", sa.Column("tracker_device_id", sa.String(80)))
    op.add_column("financing_applications", sa.Column("tracker_installed_at", sa.DateTime(timezone=True)))
    op.add_column("financing_applications", sa.Column("original_logbook_received_at", sa.DateTime(timezone=True)))

    # --- commissions
    op.create_table(
        "loan_officer_commissions",
        _uuid_pk(),
        sa.Column("loan_officer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("loan_officers.id"), nullable=False),
        sa.Column("financing_application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("financing_applications.id"), nullable=False),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("policies.id")),
        sa.Column("somosure_net_commission", sa.Numeric(14, 2)),
        sa.Column("rate_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("commission_amount", sa.Numeric(14, 2)),
        sa.Column("status", sa.String(16), nullable=False, server_default="awaiting_basis"),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("paid_by", sa.String(100)),
        sa.Column("payout_reference", sa.String(100)),
        _now("created_at"),
        _now("updated_at"),
        sa.UniqueConstraint("financing_application_id", name="uq_loan_officer_commissions_application"),
    )
    op.create_index("ix_loan_officer_commissions_officer", "loan_officer_commissions", ["loan_officer_id"])

    # --- cheques
    op.create_table(
        "financing_cheques",
        _uuid_pk(),
        sa.Column("financing_application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("financing_applications.id"), nullable=False),
        sa.Column("cheque_number", sa.String(40), nullable=False),
        sa.Column("bank_name", sa.String(80), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("cheque_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="received"),
        sa.Column("notes", sa.Text()),
        _now("received_at"),
        _now("updated_at"),
    )
    op.create_index("ix_financing_cheques_application", "financing_cheques", ["financing_application_id"])

    # --- early settlements
    op.create_table(
        "financing_settlements",
        _uuid_pk(),
        sa.Column("agreement_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("financing_agreements.id"), nullable=False),
        sa.Column("financing_application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("financing_applications.id"), nullable=False),
        sa.Column("instalments_remaining", sa.Integer(), nullable=False),
        sa.Column("outstanding_principal", sa.Numeric(14, 2), nullable=False),
        sa.Column("fee_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("fee_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_paid", sa.Numeric(14, 2), nullable=False),
        sa.Column("would_have_paid", sa.Numeric(14, 2), nullable=False),
        sa.Column("payment_reference", sa.String(100)),
        sa.Column("notes", sa.Text()),
        sa.Column("settled_by", sa.String(100)),
        _now("settled_at"),
        sa.UniqueConstraint("agreement_id", name="uq_financing_settlements_agreement"),
    )
    op.create_index("ix_financing_settlements_application", "financing_settlements", ["financing_application_id"])


def downgrade() -> None:
    op.drop_index("ix_financing_settlements_application", table_name="financing_settlements")
    op.drop_table("financing_settlements")
    op.drop_index("ix_financing_cheques_application", table_name="financing_cheques")
    op.drop_table("financing_cheques")
    op.drop_index("ix_loan_officer_commissions_officer", table_name="loan_officer_commissions")
    op.drop_table("loan_officer_commissions")
    for column in ("original_logbook_received_at", "tracker_installed_at", "tracker_device_id", "tracker_provider", "loan_officer_id", "ipf_type"):
        op.drop_column("financing_applications", column)
    op.drop_index("ix_loan_officers_staff_number", table_name="loan_officers")
    op.drop_table("loan_officers")
    for column in ("somosure_commission_pct_of_premium", "loan_officer_commission_pct", "early_settlement_fee_pct"):
        op.drop_column("financing_settings", column)
    # The minimum term is deliberately not moved back: rows set to 3 are indistinguishable
    # from rows staff chose to set to 3.
