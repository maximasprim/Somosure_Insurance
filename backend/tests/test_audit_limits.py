"""The audit trail must never be the reason a request fails (no database needed)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, inspect

from app.audit.capture import ENTITY_ID_MAX, _build_row, _entity_id
from app.models.audit import AuditLog
from app.models.user import UserRole


def test_composite_key_entity_id_fits_the_audit_column():
    # user_roles has a two-UUID primary key: 36 + 1 + 36 = 73 characters unclipped.
    row = UserRole(user_id=uuid.uuid4(), role_id=uuid.uuid4())
    entity_id = _entity_id(row, inspect(row))
    assert entity_id is not None
    assert len(entity_id) <= ENTITY_ID_MAX
    assert entity_id.startswith(str(row.user_id))  # the user stays searchable


def test_audit_row_clips_every_text_field_to_its_column():
    too_long = "x" * 2000
    row = _build_row(
        "change",
        too_long,
        datetime.now(timezone.utc),
        None,
        too_long,
        too_long,
        too_long,
        too_long,
        too_long,
        {"user_id": [None, "kept in full"]},
    )
    for column in AuditLog.__table__.columns:
        if isinstance(column.type, String) and column.type.length:
            value = getattr(row, column.name)
            if isinstance(value, str):
                assert len(value) <= column.type.length, column.name
    assert row.changes == {"user_id": [None, "kept in full"]}