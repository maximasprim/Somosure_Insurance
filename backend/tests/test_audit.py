"""The audit trail: who did what, when, and why.

Pure tests (no database) cover redaction, reason extraction and path parsing.
The rest run against the same real Postgres as the other integration tests.
"""

import json
import uuid
from decimal import Decimal

from sqlalchemy import select


# ----------------------------------------------------------------- pure tests


def test_secrets_are_redacted_and_values_are_json_safe():
    from datetime import datetime, timezone

    from app.audit.capture import clean_value

    assert clean_value("hashed_password", "$2b$12$abc") == "[redacted]"
    assert clean_value("api_key", "sk-123") == "[redacted]"
    assert clean_value("config", {"api_key": "sk-1", "region": "ke"}) == {"api_key": "[redacted]", "region": "ke"}
    assert clean_value("amount", Decimal("12.50")) == "12.50"
    assert clean_value("when", datetime(2026, 1, 2, tzinfo=timezone.utc)).startswith("2026-01-02")
    assert clean_value("id", uuid.UUID(int=1)) == str(uuid.UUID(int=1))
    assert clean_value("notes", "x" * 1000).endswith("…") and len(clean_value("notes", "x" * 1000)) == 301


def test_reason_comes_from_the_header_first_then_a_json_body():
    from app.audit.middleware import extract_reason

    assert extract_reason({"x-audit-reason": "Customer called"}, b'{"notes": "ignored"}') == "Customer called"
    assert extract_reason({}, b'{"to_status": "approved", "notes": "Documents verified"}') == "Documents verified"
    assert extract_reason({}, b'{"rejection_reason": "Fake logbook"}') == "Fake logbook"
    assert extract_reason({"x-audit-reason": "Rate%20change%20%E2%80%93%2050%25"}, None) == "Rate change – 50%"
    assert extract_reason({}, b'{"notes": "   "}') is None
    assert extract_reason({}, b"not json") is None
    assert extract_reason({}, b"[1,2]") is None
    assert extract_reason({}, None) is None


def test_entity_is_inferred_from_the_url():
    from app.audit.context import entity_from_path

    ident = "3f2b8c1e-5a4d-4e6f-9b7a-1c2d3e4f5a6b"
    assert entity_from_path(f"/api/v1/admin/applications/{ident}/transition") == ("applications", ident)
    assert entity_from_path("/api/v1/quotes") == (None, None)
    doc = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert entity_from_path(f"/api/v1/admin/applications/{ident}/documents/{doc}/url") == ("documents", doc)


def test_only_sensitive_reads_are_matched():
    from app.audit.middleware import is_sensitive_read

    assert is_sensitive_read("/api/v1/admin/applications/1/documents/2/url")
    assert is_sensitive_read("/api/v1/admin/reports/provider-performance/export.csv")
    assert not is_sensitive_read("/api/v1/admin/applications")


def test_csv_cells_cannot_be_turned_into_formulas():
    from app.api.v1.admin_audit import _csv_safe

    assert _csv_safe("=HYPERLINK(...)") == "'=HYPERLINK(...)"
    assert _csv_safe("+254700") == "'+254700"
    assert _csv_safe("normal") == "normal"
    assert _csv_safe(None) == ""


# ------------------------------------------------------------ database tests


async def _staff_token(client, db_session, email, role, name="Audit Tester"):
    from app.models.user import Role, User, UserRole

    await client.post("/api/v1/auth/register", json={"full_name": name, "email": email, "password": "supersecret1"})
    user = await db_session.scalar(select(User).where(User.email == email))
    found = await db_session.scalar(select(Role).where(Role.name == role))
    if not found:
        found = Role(id=uuid.uuid4(), name=role)
        db_session.add(found)
        await db_session.flush()
    await db_session.execute(UserRole.__table__.delete().where(UserRole.user_id == user.id))
    db_session.add(UserRole(user_id=user.id, role_id=found.id))
    await db_session.commit()
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "supersecret1"})
    return login.json()["access_token"], user


async def test_a_staff_change_is_recorded_with_who_when_what_and_why(client, db_session):
    from app.models.audit import AuditLog

    token, user = await _staff_token(client, db_session, "mgr@example.com", "management", "Mary Manager")
    auth = {"Authorization": f"Bearer {token}", "X-Audit-Reason": "Aligning with the new board-approved rate"}
    await client.get("/api/v1/admin/financing/settings", headers=auth)  # creates the singleton row if missing

    res = await client.patch("/api/v1/admin/financing/settings", json={"interest_rate_standard_monthly": "3.75"}, headers=auth)
    assert res.status_code == 200, res.text

    change = await db_session.scalar(
        select(AuditLog).where(AuditLog.kind == "change", AuditLog.entity_type == "financing_settings", AuditLog.action == "updated")
    )
    assert change is not None
    assert change.actor_type == "staff" and change.actor_role == "management"
    assert change.actor_name == "Mary Manager" and change.actor_email == "mgr@example.com"
    assert change.actor_user_id == str(user.id)
    assert change.reason == "Aligning with the new board-approved rate"
    old, new = change.changes["interest_rate_standard_monthly"]
    assert Decimal(str(old)) == Decimal("3.50") and Decimal(str(new)) == Decimal("3.75")
    assert change.occurred_at is not None and change.request_id

    request_row = await db_session.scalar(
        select(AuditLog).where(AuditLog.kind == "request", AuditLog.request_id == change.request_id)
    )
    assert request_row.status_code == 200 and request_row.method == "PATCH"
    assert request_row.reason == "Aligning with the new board-approved rate"


async def test_a_reason_in_the_request_body_is_picked_up(client, db_session):
    from app.models.audit import AuditLog

    token, _ = await _staff_token(client, db_session, "mgr2@example.com", "management")
    await client.get("/api/v1/admin/financing/settings", headers={"Authorization": f"Bearer {token}"})
    res = await client.patch(
        "/api/v1/admin/financing/settings",
        json={"max_term_months": 12, "notes": "Customers asked for a longer option"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200, res.text
    row = await db_session.scalar(
        select(AuditLog).where(AuditLog.kind == "change", AuditLog.entity_type == "financing_settings")
    )
    assert row.reason == "Customers asked for a longer option"
    assert row.changes["max_term_months"][1] == 12


async def test_refused_attempts_are_recorded_too(client, db_session):
    from app.models.audit import AuditLog

    token, _ = await _staff_token(client, db_session, "cust@example.com", "customer", "Plain Customer")
    res = await client.patch(
        "/api/v1/admin/financing/settings", json={"min_term_months": 2}, headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 403
    row = await db_session.scalar(select(AuditLog).where(AuditLog.kind == "request", AuditLog.status_code == 403))
    assert row is not None and row.method == "PATCH" and row.actor_type == "customer"


async def test_failed_login_is_recorded_without_the_password(client, db_session):
    from app.models.audit import AuditLog

    res = await client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "wrongpassword1"})
    assert res.status_code == 401
    row = await db_session.scalar(
        select(AuditLog).where(AuditLog.kind == "request", AuditLog.path == "/api/v1/auth/login", AuditLog.status_code == 401)
    )
    assert row.details["login_email"] == "nobody@example.com"
    assert "wrongpassword1" not in json.dumps(row.details) and "wrongpassword1" not in (row.summary or "")


async def test_sign_in_is_recorded_as_an_event_with_the_user(client, db_session):
    from app.models.audit import AuditLog

    await _staff_token(client, db_session, "signin@example.com", "operations", "Olive Ops")
    event = await db_session.scalar(select(AuditLog).where(AuditLog.kind == "event", AuditLog.action == "auth.login"))
    assert event.actor_name == "Olive Ops" and event.actor_role == "operations" and event.entity_type == "users"


async def test_secrets_never_reach_the_trail(client, db_session):
    from app.models.audit import AuditLog

    await client.post("/api/v1/auth/register", json={"full_name": "Secret Keeper", "email": "sk@example.com", "password": "supersecret1"})
    rows = (await db_session.scalars(select(AuditLog).where(AuditLog.entity_type == "users"))).all()
    assert rows
    blob = json.dumps([r.changes for r in rows], default=str)
    assert "supersecret1" not in blob and "$2b$" not in blob
    assert "[redacted]" in blob


async def test_guest_changes_are_attributed_to_a_guest(client, db_session, seeded_providers):
    from app.models.audit import AuditLog

    res = await client.post("/api/v1/quotes", json={"category": "medical", "answers": {"phone": "0700999000", "full_name": "Guest Person"}})
    assert res.status_code == 200
    created = await db_session.scalar(select(AuditLog).where(AuditLog.kind == "change", AuditLog.entity_type == "customers", AuditLog.action == "created"))
    assert created.actor_type == "guest" and created.actor_user_id is None


async def test_a_rolled_back_change_leaves_no_trail(client, db_session):
    from app.models.audit import AuditLog
    from app.models.content import Faq

    before = len((await db_session.scalars(select(AuditLog).where(AuditLog.entity_type == "faqs"))).all())
    db_session.add(Faq(id=uuid.uuid4(), question="Will this vanish?", answer="Yes"))
    await db_session.flush()
    await db_session.rollback()
    after = len((await db_session.scalars(select(AuditLog).where(AuditLog.entity_type == "faqs"))).all())
    assert after == before


async def test_only_management_can_read_the_trail(client, db_session):
    cust_token, _ = await _staff_token(client, db_session, "reader@example.com", "customer")
    res = await client.get("/api/v1/admin/audit", headers={"Authorization": f"Bearer {cust_token}"})
    assert res.status_code == 403

    ops_token, _ = await _staff_token(client, db_session, "ops2@example.com", "operations")
    assert (await client.get("/api/v1/admin/audit", headers={"Authorization": f"Bearer {ops_token}"})).status_code == 403

    mgr_token, _ = await _staff_token(client, db_session, "boss@example.com", "management", "Big Boss")
    page = await client.get("/api/v1/admin/audit", params={"kind": "event"}, headers={"Authorization": f"Bearer {mgr_token}"})
    assert page.status_code == 200
    body = page.json()
    assert body["total"] >= 1 and {"items", "total", "limit", "offset"} <= set(body)
    assert any(i["actor_name"] == "Big Boss" for i in body["items"])


async def test_filters_pagination_and_export(client, db_session):
    token, user = await _staff_token(client, db_session, "exp@example.com", "super_admin", "Export Person")
    auth = {"Authorization": f"Bearer {token}"}

    by_actor = (await client.get("/api/v1/admin/audit", params={"actor_user_id": str(user.id)}, headers=auth)).json()
    assert by_actor["total"] >= 1 and all(i["actor_user_id"] == str(user.id) for i in by_actor["items"])

    page = (await client.get("/api/v1/admin/audit", params={"limit": 1, "offset": 0}, headers=auth)).json()
    assert len(page["items"]) == 1 and page["total"] >= 2

    facets = (await client.get("/api/v1/admin/audit/facets", headers=auth)).json()
    assert "users" in facets["entity_types"]

    csv_res = await client.get("/api/v1/admin/audit/export.csv", headers=auth)
    assert csv_res.status_code == 200 and csv_res.headers["content-type"].startswith("text/csv")
    assert csv_res.text.splitlines()[0].startswith("time_utc,kind,actor_type")

    # exporting is itself on the record
    again = (await client.get("/api/v1/admin/audit", params={"action": "audit.exported"}, headers=auth)).json()
    assert again["total"] >= 1

    missing = await client.get(f"/api/v1/admin/audit/{uuid.uuid4()}", headers=auth)
    assert missing.status_code == 404


async def test_the_trail_cannot_be_rewritten_through_the_api(client, db_session):
    token, _ = await _staff_token(client, db_session, "nowrite@example.com", "super_admin")
    auth = {"Authorization": f"Bearer {token}"}
    some = (await client.get("/api/v1/admin/audit", params={"limit": 1}, headers=auth)).json()["items"][0]
    for method in ("put", "patch", "delete"):
        res = await getattr(client, method)(f"/api/v1/admin/audit/{some['id']}", headers=auth)
        assert res.status_code in (404, 405)
