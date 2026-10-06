"""document screening columns

Adds what the upload screening (app/services/document_validation.py) needs
to record, to both document tables:

  * validation_notes - how the file was verified, or why it was flagged
    (shown to staff beside the document);
  * file_hash - sha256 of the file, so the same file can't be uploaded as
    two different document types.

Both are nullable, so every existing row and every existing code path
keeps working untouched - documents uploaded before this migration simply
have no notes and no hash.

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-04
"""

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("application_documents", "financing_documents"):
        op.add_column(table, sa.Column("validation_notes", sa.String(500), nullable=True))
        op.add_column(table, sa.Column("file_hash", sa.String(64), nullable=True))
        op.create_index(f"ix_{table}_file_hash", table, ["file_hash"])


def downgrade() -> None:
    for table in ("application_documents", "financing_documents"):
        op.drop_index(f"ix_{table}_file_hash", table_name=table)
        op.drop_column(table, "file_hash")
        op.drop_column(table, "validation_notes")
