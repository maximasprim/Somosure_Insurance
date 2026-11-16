"""The weekly-report import through the API: preview, import, re-import, names, summary, export."""

import io
import uuid

from openpyxl import load_workbook
from sqlalchemy import select

from tests.sales_import_fixtures import build_workbook

BASE = "/api/v1/admin/sales-import"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


async def _make_user(client, db_session, email, password, role_name):
    from app.models.user import Role, User, UserRole

    await client.post("/api/v1/auth/register", json={"full_name": "Test User", "email": email, "password": password})
    user = await db_session.scalar(select(User).where(User.email == email))
    role = await db_session.scalar(select(Role).where(Role.name == role_name))
    if not role:
        role = Role(id=uuid.uuid4(), name=role_name)
        db_session.add(role)
        await db_session.flush()
    await db_session.execute(UserRole.__table__.delete().where(UserRole.user_id == user.id))
    db_session.add(UserRole(user_id=user.id, role_id=role.id))
    await db_session.commit()
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return login.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def _admin(client, db_session):
    return await _make_user(client, db_session, "finance@example.com", "supersecret1", "super_admin")


async def _upload(client, token, data, *, dry_run, name="report.xlsx", query=""):
    return await client.post(
        f"{BASE}/upload?dry_run={'true' if dry_run else 'false'}{query}",
        files={"file": (name, data, XLSX_MIME)},
        headers=_auth(token),
    )


async def test_only_finance_and_management_roles_can_use_it(client, db_session):
    token = await _make_user(client, db_session, "cust@example.com", "supersecret1", "customer")
    assert (await client.get(f"{BASE}/entries", headers=_auth(token))).status_code == 403
    assert (await _upload(client, token, build_workbook(), dry_run=True)).status_code == 403
    assert (await client.get(f"{BASE}/entries")).status_code in (401, 403)


async def test_preview_reports_what_would_happen_and_writes_nothing(client, db_session):
    token = await _admin(client, db_session)
    res = await _upload(client, token, build_workbook(), dry_run=True)
    assert res.status_code == 200, res.text
    report = res.json()
    assert report["dry_run"] is True
    assert report["counts"]["sales"] == {"new": 3, "updated": 0, "unchanged": 0, "restored": 0, "missing": 0, "total": 3}
    assert report["counts"]["claims"]["new"] == 1 and report["counts"]["ipf"]["new"] == 2
    assert report["ignored_sheets"] == ["Notes"]
    assert report["new_aliases"]["underwriters"]  # MORNACH, DIRECTLINE, KENYAN ALLIANCE
    entries = (await client.get(f"{BASE}/entries", headers=_auth(token))).json()
    assert entries["total"] == 0


async def test_import_then_import_again_changes_nothing(client, db_session):
    token = await _admin(client, db_session)
    data = build_workbook()
    first = (await _upload(client, token, data, dry_run=False)).json()
    assert first["counts"]["sales"]["new"] == 3 and first["batch_id"]

    listing = (await client.get(f"{BASE}/entries?year=2026", headers=_auth(token))).json()
    assert listing["total"] == 3
    jan = next(i for i in listing["items"] if i["client_name"] == "JOHN DOE")
    assert jan["underwriter"] == "MONARCH" and jan["start_date"] == "2026-01-06" and jan["policy_number"] == "123456"

    again = (await _upload(client, token, data, dry_run=False)).json()
    assert again["counts"]["sales"] == {"new": 0, "updated": 0, "unchanged": 3, "restored": 0, "missing": 0, "total": 3}
    assert again["already_imported"] is True
    assert (await client.get(f"{BASE}/entries", headers=_auth(token))).json()["total"] == 3
    batches = (await client.get(f"{BASE}/batches", headers=_auth(token))).json()
    assert len(batches) == 2


async def test_the_ledger_follows_the_sheet_edits_and_removals(client, db_session):
    token = await _admin(client, db_session)
    await _upload(client, token, build_workbook(), dry_run=False)

    # premium corrected in the sheet, and the February row deleted
    report = (await _upload(client, token, build_workbook(premium_jan=51000, include_february=False), dry_run=False)).json()
    sales = report["counts"]["sales"]
    assert (sales["new"], sales["updated"], sales["missing"]) == (0, 1, 1)
    change = report["changes"][0]
    assert change["client_name"] == "JOHN DOE" and {f["field"] for f in change["fields"]} >= {"premium", "commission"}

    missing = (await client.get(f"{BASE}/entries?status=missing_from_sheet", headers=_auth(token))).json()
    assert [i["client_name"] for i in missing["items"]] == ["PETER KAMAU"]  # kept, marked - never deleted
    john = (await client.get(f"{BASE}/entries?q=JOHN", headers=_auth(token))).json()["items"][0]
    assert john["premium"] == "51000.00"

    # and it comes back when the row returns to the sheet
    back = (await _upload(client, token, build_workbook(premium_jan=51000), dry_run=False)).json()
    assert back["counts"]["sales"]["restored"] == 1


async def test_claims_are_kept_with_their_timeline_and_linked_to_the_sale(client, db_session):
    token = await _admin(client, db_session)
    await _upload(client, token, build_workbook(), dry_run=False)
    claims = (await client.get(f"{BASE}/claims?year=2026", headers=_auth(token))).json()
    assert len(claims) == 1
    claim = claims[0]
    assert claim["date_reported"] == "2026-05-03" and claim["outcome"] == "closed"
    assert [m["event"] for m in claim["milestones"]] == ["reported", "documents_submitted", "release_letter"]
    assert claim["sales_entry_id"] is not None
    ipf = (await client.get(f"{BASE}/ipf?year=2026", headers=_auth(token))).json()
    assert len(ipf) == 2


async def test_names_can_be_reviewed_edited_and_re_applied(client, db_session):
    token = await _admin(client, db_session)
    await _upload(client, token, build_workbook(), dry_run=False)

    aliases = (await client.get(f"{BASE}/aliases?kind=underwriter&unconfirmed=true", headers=_auth(token))).json()
    morn = next(a for a in aliases if a["alias_key"] == "MORNACH")
    assert morn["canonical"] == "MONARCH" and morn["confirmed"] is False

    res = await client.put(f"{BASE}/aliases/{morn['id']}", json={"canonical": "Monarch General", "confirmed": True}, headers=_auth(token))
    assert res.status_code == 200 and res.json()["canonical"] == "MONARCH GENERAL"

    applied = (await client.post(f"{BASE}/aliases/reapply", headers=_auth(token))).json()
    assert applied["sales_rows"] >= 1
    found = (await client.get(f"{BASE}/entries?underwriter=MONARCH GENERAL", headers=_auth(token))).json()
    assert found["total"] == 1

    created = await client.post(f"{BASE}/aliases", json={"kind": "staff", "typed": "J. Osphine - H.Q.", "canonical": "Josphine", "branch": "hq"}, headers=_auth(token))
    assert created.status_code == 201 and created.json()["branch"] == "HQ"
    duplicate = await client.post(f"{BASE}/aliases", json={"kind": "staff", "typed": "J. Osphine - H.Q.", "canonical": "X"}, headers=_auth(token))
    assert duplicate.status_code == 400


async def test_summary_groups_the_ledger(client, db_session):
    token = await _admin(client, db_session)
    await _upload(client, token, build_workbook(), dry_run=False)
    summary = (await client.get(f"{BASE}/summary?year=2026", headers=_auth(token))).json()
    assert [m["month"] for m in summary["monthly"]] == [1, 2]
    assert {r["underwriter"] for r in summary["by_underwriter"]} == {"MONARCH", "DIRECT LINE", "KENYA ALLIANCE"}
    assert {r["product"] for r in summary["by_product"]} == {"motor", "professional_indemnity"}
    options = (await client.get(f"{BASE}/entries/options?year=2026", headers=_auth(token))).json()
    assert options["years"] == [2026] and "HQ" in options["branches"]


async def test_the_cleaned_workbook_downloads_and_imports_back_unchanged(client, db_session):
    token = await _admin(client, db_session)
    await _upload(client, token, build_workbook(), dry_run=False)

    res = await client.get(f"{BASE}/export?years=2026", headers=_auth(token))
    assert res.status_code == 200 and res.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert "2026 Sales" in load_workbook(io.BytesIO(res.content)).sheetnames

    again = (await _upload(client, token, res.content, dry_run=True, name="cleaned.xlsx")).json()
    sales = again["counts"]["sales"]
    assert (sales["new"], sales["updated"], sales["missing"]) == (0, 0, 0)


async def test_files_that_are_not_workbooks_are_refused(client, db_session):
    token = await _admin(client, db_session)
    bad = await _upload(client, token, b"not a workbook", dry_run=True)
    assert bad.status_code == 400 and "Excel" in bad.json()["detail"]
    csv = await _upload(client, token, b"a,b\n1,2", dry_run=True, name="report.csv")
    assert csv.status_code == 400


async def test_the_period_limits_the_import_and_leaves_earlier_rows_alone(client, db_session):
    token = await _admin(client, db_session)
    data = build_workbook()

    preview = (await _upload(client, token, data, dry_run=True, query="&from_period=2026-02")).json()
    assert preview["counts"]["sales"]["new"] == 1
    assert preview["period"]["from"] == "2026-02" and preview["period"]["skipped"]["sales"] == 2

    await _upload(client, token, data, dry_run=False)  # everything
    # February's row removed from the sheet; only February onward is being imported
    report = (await _upload(client, token, build_workbook(include_february=False), dry_run=False, query="&from_period=2026-02")).json()
    assert report["counts"]["sales"]["missing"] == 1
    missing = (await client.get(f"{BASE}/entries?status=missing_from_sheet", headers=_auth(token))).json()
    assert [i["client_name"] for i in missing["items"]] == ["PETER KAMAU"]
    active = (await client.get(f"{BASE}/entries?status=active", headers=_auth(token))).json()
    assert active["total"] == 2  # January untouched

    bad = await client.post(f"{BASE}/upload?dry_run=true&from_period=2026-13", files={"file": ("r.xlsx", data, XLSX_MIME)}, headers=_auth(token))
    assert bad.status_code == 422


async def test_suggested_fixes_are_accepted_one_by_one_and_survive_re_uploads(client, db_session):
    token = await _admin(client, db_session)
    data = build_workbook(include_year_typo=True)
    await _upload(client, token, data, dry_run=False)

    waiting = (await client.get(f"{BASE}/suggestions?year=2026", headers=_auth(token))).json()
    assert len(waiting) == 1
    fix = waiting[0]
    assert (fix["client_name"], fix["field"], fix["current"], fix["suggested"]) == ("ANN WANJIRU", "start_date", "2027-03-14", "2026-03-14")

    # a value the importer did not suggest is refused
    wrong = await client.post(f"{BASE}/suggestions/apply", json={"items": [{"entry_id": fix["entry_id"], "field": "start_date", "value": "2026-03-15"}]}, headers=_auth(token))
    assert wrong.json()["applied"] == 0 and wrong.json()["skipped"]

    ok = await client.post(f"{BASE}/suggestions/apply", json={"items": [{"entry_id": fix["entry_id"], "field": fix["field"], "value": fix["suggested"]}]}, headers=_auth(token))
    assert ok.json()["applied"] == 1
    row = (await client.get(f"{BASE}/entries?q=ANN", headers=_auth(token))).json()["items"][0]
    assert row["start_date"] == "2026-03-14" and row["issue_level"] == "info"
    assert any(f["code"] == "fix_applied" for f in row["flags"])
    assert (await client.get(f"{BASE}/suggestions", headers=_auth(token))).json() == []

    # the sheet still has the old year; uploading it again must not undo the accepted fix
    again = (await _upload(client, token, data, dry_run=False)).json()
    assert again["counts"]["sales"]["updated"] == 0
    row = (await client.get(f"{BASE}/entries?q=ANN", headers=_auth(token))).json()["items"][0]
    assert row["start_date"] == "2026-03-14"
