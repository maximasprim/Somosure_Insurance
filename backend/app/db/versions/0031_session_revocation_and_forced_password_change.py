"""session revocation and forced password change

Two columns on users. token_version lets an administrator (or a password change)
sign a user out of every device at once: tokens carry the version they were issued
under and stop working when it moves on. must_change_password makes a user pick a
new password at their next sign-in (used after an administrator sets one for them).
Additive; existing users get version 0 and no forced change, and tokens already
issued keep working until something bumps the version.

Revision ID: 0031
Revises: 0030
Create Date: 2026-11-08
"""

import sqlalchemy as sa
from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("users", "must_change_password")
    op.drop_column("users", "token_version")
