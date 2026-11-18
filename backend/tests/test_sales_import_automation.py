"""Automatic Google Sheet import, import versions, and reverting to an earlier version."""

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import func, select

from app.services.sales_import import google_sheet, schedule
from app.services.sales_import.google_sheet import SheetFetchError, SheetLinkError
from tests.sales_import_fixtures import build_workbook
from tests.test_sales_import_api import _admin, _auth, _make_user, _upload
from tests.test_sales_post_api import _count, _link_everyone, _provider

B = "/api/v1/admin/sales-import"
SHEET_ID = "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit#gid=0"

V1 = build_workbook(include_second_row=False, include_february=False)  # one sale
V2 = build_workbook()  # three sales
V3 = build_workbook(premium_jan=51000)  # three sales, one premium changed


class FakeSheet:
    """Stands in for Google: whatever `.data` holds is what the next pull downloads."""

    def __init__(self, monkeypatch):
        self.data: bytes | Exception = V2
        self.calls = 0

        async def fetch(sheet_id, **_):
            self.calls += 1
            assert sheet_id == SHEET_ID
            if isinstance(self.data, Exception):
                raise self.data
            return self.data

        monkeypatch.setattr(google_sheet, "fetch_workbook", fetch)


@pytest.fixture
def sheet(monkeypatch):
    return FakeSheet(monkeypatch)


async def _settings(client, token, **over):
    body = {"sheet_url": SHEET_URL, "enabled": True, "frequency": "weekly", "weekday": 0, "hour": 6, **over}
    return await client.put(f"{B}/automation", json=body, headers=_auth(token))


async def _versions(client, token):
    return (await client.get(f"{B}/versions", headers=_auth(token))).json()["items"]


# ------------------------------------------------------------------------------------ pure rules


def test_next_run_is_always_strictly_after_now_in_nairobi_time():
    tue_noon_eat = datetime(2026, 11, 17, 9, 0, tzinfo=timezone.utc)  # Tuesday 12:00 in Nairobi
    assert schedule.next_run_after(tue_noon_eat, frequency="weekly", weekday=0, hour=6) == datetime(2026, 11, 23, 3, 0, tzinfo=timezone.utc)
    assert schedule.next_run_after(tue_noon_eat, frequency="weekly", weekday=1, hour=13) == datetime(2026, 11, 17, 10, 0, tzinfo=timezone.utc)  # later today
    assert schedule.next_run_after(tue_noon_eat, frequency="weekly", weekday=1, hour=12) == datetime(2026, 11, 24, 9, 0, tzinfo=timezone.utc)  # exactly now -> next week
    assert schedule.next_run_after(tue_noon_eat, frequency="daily", hour=6) == datetime(2026, 11, 18, 3, 0, tzinfo=timezone.utc)
    assert schedule.next_run_after(tue_noon_eat, frequency="monthly", day_of_month=1, hour=6) == datetime(2026, 12, 1, 3, 0, tzinfo=timezone.utc)
    dec = datetime(2026, 12, 20, 9, 0, tzinfo=timezone.utc)
    assert schedule.next_run_after(dec, frequency="monthly", day_of_month=5, hour=6) == datetime(2027, 1, 5, 3, 0, tzinfo=timezone.utc)  # year rolls over
    assert schedule.next_run_after(dec, frequency="monthly", day_of_month=31, hour=6).day == 28  # capped so every month has the day
    with pytest.raises(ValueError):
        schedule.next_run_after(dec, frequency="hourly")
    assert schedule.describe("weekly", 0, 1, 6) == "Every Monday at 06:00 (Nairobi time)"


def test_only_real_google_sheet_links_are_accepted():
    assert google_sheet.parse_sheet_link(SHEET_URL) == SHEET_ID
    assert google_sheet.parse_sheet_link(f"https://docs.google.com/spreadsheets/d/{SHEET_ID}") == SHEET_ID
    assert google_sheet.parse_sheet_link(SHEET_ID) == SHEET_ID
    for bad in (
        "", "hello", "http://docs.google.com/spreadsheets/d/" + SHEET_ID,  # not https
        "https://evil.example.com/?u=https://docs.google.com/spreadsheets/d/" + SHEET_ID,  # something else dressed up as a sheet link
        "https://docs.google.com.evil.example.com/spreadsheets/d/" + SHEET_ID,
        "https://docs.google.com/spreadsheets/d/short",
        "https://docs.google.com/document/d/" + SHEET_ID,
    ):
        with pytest.raises(SheetLinkError):
            google_sheet.parse_sheet_link(bad)
    with pytest.raises(SheetLinkError, match="Drive"):
        google_sheet.parse_sheet_link("https://drive.google.com/file/d/" + SHEET_ID + "/view")


def _client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)


async def test_download_explains_why_google_refused():
    seen = []

    def ok(request):
        seen.append(str(request.url))
        return httpx.Response(200, content=V1, headers={"content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"})

    assert await google_sheet.fetch_workbook(SHEET_ID, client=_client(ok)) == V1
    assert seen == [f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx"]  # the address is built here, never taken from the link box

    def answer(status, body=b"", ctype="text/html", location=None):
        def handler(request):
            headers = {"content-type": ctype, **({"location": location} if location else {})}
            return httpx.Response(status, content=body, headers=headers)
        return handler

    for handler, text in (
        (answer(403), "private"),
        (answer(404), "does not exist"),
        (answer(429), "rate-limiting"),
        (answer(500), "error"),
        (answer(200, b"<html>sign in</html>"), "private"),  # Google's login page, served with 200
        (answer(200, b"not a workbook", ctype="application/octet-stream"), "not an Excel workbook"),
    ):
        with pytest.raises(SheetFetchError, match=text):
            await google_sheet.fetch_workbook(SHEET_ID, client=_client(handler))

    def to_login(request):
        if request.url.host == "accounts.google.com":
            return httpx.Response(200, content=b"<html>login</html>", headers={"content-type": "text/html"})
        return httpx.Response(302, headers={"location": "https://accounts.google.com/ServiceLogin"})

    with pytest.raises(SheetFetchError, match="private"):
        await google_sheet.fetch_workbook(SHEET_ID, client=_client(to_login))

    def boom(request):
        raise httpx.ConnectError("no route")

    with pytest.raises(SheetFetchError, match="Could not reach Google"):
        await google_sheet.fetch_workbook(SHEET_ID, client=_client(boom))

    monkey_limit = google_sheet.MAX_BYTES
    google_sheet.MAX_BYTES = 10
    try:
        with pytest.raises(SheetFetchError, match="15MB"):
            await google_sheet.fetch_workbook(SHEET_ID, client=_client(ok))
    finally:
        google_sheet.MAX_BYTES = monkey_limit


# ------------------------------------------------------------------------------------ the settings form


async def test_settings_need_the_right_role_and_a_real_link(client, db_session):
    customer = await _make_user(client, db_session, "cust@example.com", "supersecret1", "customer")
    assert (await client.get(f"{B}/automation", headers=_auth(customer))).status_code == 403

    finance = await _make_user(client, db_session, "fo@example.com", "supersecret1", "finance_officer")
    assert (await client.get(f"{B}/automation", headers=_auth(finance))).status_code == 200  # may look...
    assert (await _settings(client, finance)).status_code == 403  # ...not change
    assert (await client.post(f"{B}/automation/run-now", headers=_auth(finance))).status_code == 403

    admin = await _admin(client, db_session)
    first = (await client.get(f"{B}/automation", headers=_auth(admin))).json()
    assert first["settings"]["enabled"] is False and first["settings"]["sheet_url"] is None and first["runs"] == []

    bad = await _settings(client, admin, sheet_url="https://example.com/not-a-sheet")
    assert bad.status_code == 400 and "docs.google.com" in bad.json()["detail"]
    assert (await _settings(client, admin, sheet_url="")).status_code == 400  # switched on with no link
    assert (await _settings(client, admin, hour=24)).status_code == 422
    assert (await _settings(client, admin, frequency="hourly")).status_code == 422
    assert (await _settings(client, admin, period_from="2026-05", period_to="2026-01")).status_code == 400


async def test_saving_schedules_the_next_run_and_switching_off_clears_it(client, db_session):
    admin = await _admin(client, db_session)
    saved = (await _settings(client, admin, frequency="weekly", weekday=0, hour=6)).json()
    assert saved["enabled"] and saved["schedule_text"] == "Every Monday at 06:00 (Nairobi time)"
    due = datetime.fromisoformat(saved["next_run_at"])
    assert due > datetime.now(timezone.utc) and due.astimezone(schedule.EAT).weekday() == 0 and due.astimezone(schedule.EAT).hour == 6

    off = (await _settings(client, admin, enabled=False)).json()
    assert off["enabled"] is False and off["next_run_at"] is None and off["sheet_url"] == SHEET_URL  # the link is kept


# ------------------------------------------------------------------------------------ versions


async def test_every_import_becomes_a_numbered_version_with_its_file(client, db_session):
    admin = await _admin(client, db_session)
    assert await _versions(client, admin) == []
    await _upload(client, admin, V1, dry_run=True)
    assert await _versions(client, admin) == []  # a check saves nothing

    first = (await _upload(client, admin, V1, dry_run=False, name="week1.xlsx")).json()
    await _upload(client, admin, V2, dry_run=False, name="week2.xlsx")
    items = await _versions(client, admin)
    assert [(v["version_no"], v["source"], v["filename"], v["is_current"]) for v in items] == [(2, "manual", "week2.xlsx", True), (1, "manual", "week1.xlsx", False)]
    assert first["version_no"] == 1 and items[1]["created_by_name"] == "Test User" and items[1]["size_bytes"] == len(V1)
    assert items[1]["counts"]["sales"]["new"] == 1

    got = await client.get(f"{B}/versions/{items[1]['id']}/download", headers=_auth(admin))
    assert got.status_code == 200 and got.content == V1  # byte-for-byte the file that was imported
    assert "sales-report-v1.xlsx" in got.headers["content-disposition"]
    assert (await client.get(f"{B}/versions/00000000-0000-0000-0000-000000000000/download", headers=_auth(admin))).status_code == 404


async def test_a_refused_upload_leaves_no_version(client, db_session):
    admin = await _admin(client, db_session)
    assert (await _upload(client, admin, b"this is not a workbook", dry_run=False)).status_code == 400
    assert await _versions(client, admin) == []


# ------------------------------------------------------------------------------------ pulling the sheet


async def test_run_now_imports_what_changed_and_skips_what_did_not(client, db_session, sheet):
    admin = await _admin(client, db_session)
    assert (await client.post(f"{B}/automation/run-now", headers=_auth(admin))).status_code == 400  # no link yet

    await _settings(client, admin, enabled=False)
    first = (await client.post(f"{B}/automation/run-now", headers=_auth(admin))).json()
    assert first["status"] == "imported" and "version 1" in first["message"] and "3 new" in first["message"]
    assert [(v["version_no"], v["source"]) for v in await _versions(client, admin)] == [(1, "google_sheet")]

    again = (await client.post(f"{B}/automation/run-now", headers=_auth(admin))).json()
    assert again["status"] == "no_changes" and len(await _versions(client, admin)) == 1  # same file: no new version

    # Google re-exports the same content as different bytes: still nothing to import, still no version
    sheet.data = build_workbook() + b""
    from openpyxl import load_workbook
    import io
    wb = load_workbook(io.BytesIO(V2))
    wb.properties.title = "touched"  # different bytes, same rows
    out = io.BytesIO()
    wb.save(out)
    sheet.data = out.getvalue()
    assert sheet.data != V2
    same = (await client.post(f"{B}/automation/run-now", headers=_auth(admin))).json()
    assert same["status"] == "no_changes" and len(await _versions(client, admin)) == 1

    sheet.data = V3
    changed = (await client.post(f"{B}/automation/run-now", headers=_auth(admin))).json()
    assert changed["status"] == "imported" and "1 changed" in changed["message"]
    latest = (await _versions(client, admin))[0]
    assert (latest["version_no"], latest["is_current"], latest["created_by_name"]) == (2, True, "Test User")

    runs = (await client.get(f"{B}/automation", headers=_auth(admin))).json()
    assert [r["status"] for r in runs["runs"]] == ["imported", "no_changes", "no_changes", "imported"]
    assert runs["settings"]["last_status"] == "imported"


async def test_a_failed_pull_is_recorded_and_changes_nothing(client, db_session, sheet):
    admin = await _admin(client, db_session)
    await _settings(client, admin, enabled=False)
    sheet.data = SheetFetchError("The sheet is private. Share it.")
    res = (await client.post(f"{B}/automation/run-now", headers=_auth(admin))).json()
    assert res["status"] == "failed" and "private" in res["message"]
    state = (await client.get(f"{B}/automation", headers=_auth(admin))).json()
    assert state["settings"]["last_status"] == "failed" and state["settings"]["consecutive_failures"] == 1
    assert state["runs"][0]["status"] == "failed" and await _versions(client, admin) == []

    sheet.data = RuntimeError("boom")  # an unexpected crash is also contained, and the user sees a safe message
    res = (await client.post(f"{B}/automation/run-now", headers=_auth(admin))).json()
    assert res["status"] == "failed" and "server log" in res["message"] and "boom" not in res["message"]

    sheet.data = b"PK-but-not-really"  # looks like a zip, is not a workbook
    res = (await client.post(f"{B}/automation/run-now", headers=_auth(admin))).json()
    assert res["status"] == "failed" and await _versions(client, admin) == []

    sheet.data = V1
    assert (await client.post(f"{B}/automation/run-now", headers=_auth(admin))).json()["status"] == "imported"
    assert (await client.get(f"{B}/automation", headers=_auth(admin))).json()["settings"]["consecutive_failures"] == 0  # recovered


async def test_the_scheduler_job_only_runs_when_due_and_reschedules(client, db_session, session_factory, sheet):
    from app.models.sales_automation import SalesImportSettings
    from app.services.sales_import.auto_import import run_due_sales_import

    async def tick():
        async with session_factory() as s:
            return await run_due_sales_import(s)

    admin = await _admin(client, db_session)
    assert (await tick())["status"] == "idle"  # off

    await _settings(client, admin)
    assert (await tick()) == {"status": "idle", "reason": "not due yet"} and sheet.calls == 0

    async def make_due():
        db_session.expire_all()
        row = await db_session.get(SalesImportSettings, 1)
        row.next_run_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        await db_session.commit()

    await make_due()
    done = await tick()
    assert done["status"] == "imported" and sheet.calls == 1
    db_session.expire_all()
    row = await db_session.get(SalesImportSettings, 1)
    assert row.next_run_at > datetime.now(timezone.utc) + timedelta(days=1)  # back on its weekly slot
    assert (await tick())["status"] == "idle" and sheet.calls == 1  # not twice

    # a failure is retried in hours, not a week - but only a few times, then it waits for the normal slot
    sheet.data = SheetFetchError("Google is down")
    await make_due()
    assert (await tick())["status"] == "failed"
    db_session.expire_all()
    row = await db_session.get(SalesImportSettings, 1)
    assert timedelta(hours=5) < row.next_run_at - datetime.now(timezone.utc) < timedelta(hours=7)
    for _ in range(3):
        await make_due()
        await tick()
    db_session.expire_all()
    row = await db_session.get(SalesImportSettings, 1)
    assert row.consecutive_failures == 4 and row.next_run_at - datetime.now(timezone.utc) > timedelta(days=1)


def test_the_scheduler_knows_the_job():
    from app.services.scheduler import JOBS

    assert "sales_import" in {j.name for j in JOBS}


# ------------------------------------------------------------------------------------ reverting


async def test_revert_puts_the_old_values_back_and_is_itself_a_version(client, db_session):
    from app.models.sales_ledger import SalesEntry

    admin = await _admin(client, db_session)
    await _upload(client, admin, V2, dry_run=False)
    await _upload(client, admin, V3, dry_run=False)
    john = lambda: db_session.scalar(select(SalesEntry.premium).where(SalesEntry.policy_number == "123456"))
    db_session.expire_all()
    assert await john() == 51000
    v = {x["version_no"]: x["id"] for x in await _versions(client, admin)}

    assert (await client.post(f"{B}/versions/{v[2]}/revert", json={}, headers=_auth(admin))).status_code == 409  # already current

    preview = (await client.get(f"{B}/versions/{v[1]}/revert-preview", headers=_auth(admin))).json()
    assert preview["version_no"] == 1 and preview["counts"]["sales"]["updated"] == 1 and preview["posted_to_remove"] == 0
    db_session.expire_all()
    assert await john() == 51000 and len(await _versions(client, admin)) == 2  # a preview changes nothing

    res = await client.post(f"{B}/versions/{v[1]}/revert", json={"reason": "Wrong premium typed in the sheet"}, headers=_auth(admin))
    assert res.status_code == 200, res.text
    assert res.json()["restored"] == 1 and res.json()["version_no"] == 3
    db_session.expire_all()
    assert await john() == 50000

    items = await _versions(client, admin)
    top = items[0]
    assert (top["version_no"], top["source"], top["reverted_to_version_no"], top["note"], top["is_current"]) == (3, "revert", 1, "Wrong premium typed in the sheet", True)
    assert items[1]["is_current"] is False and len(items) == 3  # history kept, nothing rewritten

    # and the revert can itself be undone, by going to the version before it
    assert (await client.post(f"{B}/versions/{v[2]}/revert", json={}, headers=_auth(admin))).status_code == 200
    db_session.expire_all()
    assert await john() == 51000 and len(await _versions(client, admin)) == 4


async def test_revert_removes_what_was_posted_for_rows_the_old_version_did_not_have(client, db_session):
    from app.models.payment import Payment
    from app.models.policy import Policy
    from app.models.sales_ledger import SalesEntry

    token = await _admin(client, db_session)
    await _provider(db_session, "Monarch Insurance Company")
    await _upload(client, token, V1, dry_run=False)  # version 1: one sale
    await _upload(client, token, V2, dry_run=False)  # version 2: three sales
    await _link_everyone(client, token)
    P = f"{B}/posting"
    assert (await client.post(f"{P}/run?dry_run=false", headers=_auth(token))).json()["posted"] == 3
    assert await _count(db_session, Policy) == 3 and await _count(db_session, Payment) == 3

    # a platform policy and a sale typed in by hand must survive any revert
    from tests.test_sales_sync_api import _seed_policy
    providers = (await db_session.scalars(select(__import__("app.models.provider", fromlist=["x"]).InsuranceProvider))).all()
    await _seed_policy(db_session, providers[0], "PLAT-KEEP", "20000", name="Online Buyer")
    await db_session.execute(SalesEntry.__table__.update().where(SalesEntry.client_name == "PETER KAMAU").values(origin="manual"))
    await db_session.commit()

    v1 = [x for x in await _versions(client, token) if x["version_no"] == 1][0]["id"]
    preview = (await client.get(f"{B}/versions/{v1}/revert-preview", headers=_auth(token))).json()
    assert preview["posted_to_remove"] == 1 and preview["missing_total"] == 1  # Jane only: Peter was typed in, not imported
    assert await _count(db_session, Policy) == 4  # still a preview

    res = (await client.post(f"{B}/versions/{v1}/revert", json={}, headers=_auth(token))).json()
    assert res["posting"]["unposted"] == {"removed": 1, "kept": 0}

    db_session.expire_all()
    numbers = sorted((await db_session.scalars(select(Policy.policy_number))).all())
    assert "PLAT-KEEP" in numbers and "123456" in numbers and len(numbers) == 3  # John (in v1), Peter (manual), the platform's own
    jane = await db_session.scalar(select(SalesEntry).where(SalesEntry.client_name == "JANE ROE"))
    assert jane.status == "missing_from_sheet" and jane.posted_at is None and jane.policy_id is None  # kept in the ledger, no longer posted
    peter = await db_session.scalar(select(SalesEntry).where(SalesEntry.client_name == "PETER KAMAU"))
    assert peter.status == "active" and peter.posted_at is not None


async def test_revert_pauses_automatic_imports_until_someone_resumes(client, db_session, session_factory, sheet):
    from app.models.sales_automation import SalesImportSettings
    from app.services.sales_import.auto_import import run_due_sales_import

    admin = await _admin(client, db_session)
    await _upload(client, admin, V1, dry_run=False)
    await _upload(client, admin, V2, dry_run=False)
    await _settings(client, admin)
    v1 = [x for x in await _versions(client, admin) if x["version_no"] == 1][0]["id"]

    assert (await client.get(f"{B}/versions/{v1}/revert-preview", headers=_auth(admin))).json()["will_pause_automation"] is True
    res = (await client.post(f"{B}/versions/{v1}/revert", json={}, headers=_auth(admin))).json()
    assert res["automation_paused"] is True
    state = (await client.get(f"{B}/automation", headers=_auth(admin))).json()["settings"]
    assert state["enabled"] is True and "version 1" in state["paused_reason"] and state["next_run_at"] is None

    db_session.expire_all()
    row = await db_session.get(SalesImportSettings, 1)
    row.next_run_at = datetime.now(timezone.utc) - timedelta(hours=1)  # even if it were overdue...
    await db_session.commit()
    async with session_factory() as s:
        assert (await run_due_sales_import(s)) == {"status": "idle", "reason": "paused"}  # ...it does not run
    assert sheet.calls == 0

    saved = (await _settings(client, admin, hour=7)).json()  # editing other settings does not silently un-pause
    assert saved["paused_reason"] and saved["next_run_at"] is None

    resumed = (await client.post(f"{B}/automation/resume", headers=_auth(admin))).json()
    assert resumed["paused_reason"] is None and datetime.fromisoformat(resumed["next_run_at"]) > datetime.now(timezone.utc)


async def test_revert_needs_manage_rights_and_a_readable_file(client, db_session, tmp_path):
    admin = await _admin(client, db_session)
    await _upload(client, admin, V1, dry_run=False)
    await _upload(client, admin, V2, dry_run=False)
    v1 = [x for x in await _versions(client, admin) if x["version_no"] == 1][0]

    finance = await _make_user(client, db_session, "fo@example.com", "supersecret1", "finance_officer")
    assert (await client.post(f"{B}/versions/{v1['id']}/revert", json={}, headers=_auth(finance))).status_code == 403
    assert (await client.get(f"{B}/versions/{v1['id']}/revert-preview", headers=_auth(finance))).status_code == 403
    assert (await client.get(f"{B}/versions", headers=_auth(finance))).status_code == 200  # may see the history
    assert (await client.post(f"{B}/versions/00000000-0000-0000-0000-000000000000/revert", json={}, headers=_auth(admin))).status_code == 404

    for f in (tmp_path / "workbooks").rglob("*.xlsx"):  # the stored copy is lost
        f.unlink()
    res = await client.post(f"{B}/versions/{v1['id']}/revert", json={}, headers=_auth(admin))
    assert res.status_code == 409 and "could not be read back" in res.json()["detail"]
    assert (await client.get(f"{B}/versions/{v1['id']}/download", headers=_auth(admin))).status_code == 409
    assert len(await _versions(client, admin)) == 2  # and nothing was half-done


# ------------------------------------------------------------------------------------ storage outage


class _BrokenStorage:
    async def save(self, *a, **k):
        raise ConnectionError("storage is down")


async def test_if_the_file_cannot_be_kept_the_import_is_refused_and_nothing_changes(client, db_session, sheet, monkeypatch, sales_workbook_storage):
    """A version that cannot be restored must never exist, so a storage outage stops the import instead of
    importing without keeping the file."""
    from app.models.sales_ledger import ImportBatch, SalesEntry
    from app.services.sales_import import versions

    admin = await _admin(client, db_session)
    monkeypatch.setattr(versions, "get_storage", lambda: _BrokenStorage())

    res = await _upload(client, admin, V2, dry_run=False)
    assert res.status_code == 503 and "could not be saved to storage" in res.json()["detail"] and "storage is down" not in res.json()["detail"]
    assert await _count(db_session, SalesEntry) == 0 and await _count(db_session, ImportBatch) == 0 and await _versions(client, admin) == []
    assert (await _upload(client, admin, V2, dry_run=True)).status_code == 200  # a check needs no storage

    await _settings(client, admin, enabled=False)
    pulled = (await client.post(f"{B}/automation/run-now", headers=_auth(admin))).json()
    assert pulled["status"] == "failed" and "could not be saved to storage" in pulled["message"]
    assert await _count(db_session, SalesEntry) == 0 and await _versions(client, admin) == []

    monkeypatch.setattr(versions, "get_storage", lambda: sales_workbook_storage)  # storage is back: the same import now works
    assert (await _upload(client, admin, V2, dry_run=False)).status_code == 200
    assert await _count(db_session, SalesEntry) == 3
