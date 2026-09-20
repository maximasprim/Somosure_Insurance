"""widen rate_card basis and source_document columns

RateCardExtension.basis / RateCardExcess.basis were created as
VARCHAR(20) in 0012, but "percent_of_sum_insured" is 22 characters -
confirmed failing on a real Postgres insert (StringDataRightTruncation).
Separately, RateCardVehicleClass.source_document was VARCHAR(255), and
the Pioneer Insurance Kenya disclosure note (explaining its rate card
didn't parse cleanly) is 271 characters. Widening both here rather than
editing 0012 in place, since 0012 may already be applied against a real
database.

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-19
"""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("rate_card_extensions", "basis", type_=sa.String(30))
    op.alter_column("rate_card_excesses", "basis", type_=sa.String(30))
    op.alter_column("rate_card_vehicle_classes", "source_document", type_=sa.String(500))


def downgrade() -> None:
    op.alter_column("rate_card_extensions", "basis", type_=sa.String(20))
    op.alter_column("rate_card_excesses", "basis", type_=sa.String(20))
    op.alter_column("rate_card_vehicle_classes", "source_document", type_=sa.String(255))