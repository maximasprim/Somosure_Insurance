"""Recording a sale directly in the system, like adding a row to the weekly sheet."""

import uuid
from datetime import date, timedelta

from sqlalchemy import func, select, update

from tests.sales_import_fixtures import build_workbook
from tests.test_sales_import_api import _admin, _auth, _make_user, _upload
from tests.test_sales_post_api import P, _count, _link_everyone, _provider

S = "/api/v1/admin/sales"


def _sale(provider_id, **over):
    base = {
        "client_name": "Peter Kamau", "provider_id": str(provider_id), "reg_or_product": "KDM 813Y", "start_date": "2026-02-03",
        "date_paid": "2026-02-03", "staff_name": "wilson", "branch": "ruiru", "policy_number": "ABC/999", "premium": "30000", "commission": "3000",
    }
    return {**base, **over}


async def test_the_form_offers_providers_staff_and_branches(client, db_session):
    token = await _admin(client, db_session)
    await _provider(db_session, "Monarch Insurance Company")
    await _upload(client, token, build_workbook(), dry_run=False)
    options = (await client.get(f"{S}/record/options", headers=_auth(token))).json()
    monarch = next(p for p in options["providers"] if p["name"] == "Monarch Insurance Company")
    assert monarch["underwriter"] == "MONARCH"
    assert "HQ" in options["branches"] and "WIBA" in options["product_hints"] and options["wht_rate"] == "0.10"


async def test_a_recorded_sale_becomes_a_real_policy_and_a_sheet_style_row(client, db_session):
    from app.models.customer import Customer
    from app.models.payment import Payment
    from app.models.policy import Policy
    from app.models.sales_ledger import SalesEntry

    token = await _admin(client, db_session)
    provider = await _provider(db_session, "Kenya Alliance Insurance")
    res = await client.post(f"{S}/record", json=_sale(provider.id), headers=_auth(token))
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["created"] is True and out["policy_number"] == "ABC/999" and out["customer_existed"] is False
    assert {f["code"] for f in out["flags"]} == {"customer_no_phone"}  # missing detail flagged, sale still recorded

    policy = await db_session.scalar(select(Policy).where(Policy.policy_number == "ABC/999"))
    assert policy.source == "workbook" and policy.premium == 30000 and (policy.start_date, policy.end_date) == (date(2026, 2, 3), date(2027, 2, 2))
    assert (await db_session.scalar(select(Payment.amount).where(Payment.policy_id == policy.id))) == 30000
    row = await db_session.scalar(select(SalesEntry).where(SalesEntry.policy_number == "ABC/999"))
    assert row.origin == "manual" and row.sheet_name == "Entered in system" and row.period_month == 2 and row.client_name == "PETER KAMAU"
    assert (row.staff_name, row.branch, row.reg_no) == ("Wilson", "RUIRU", "KDM813Y")
    assert (row.commission, row.wht, row.net_revenue) == (3000, 300, 2700)  # tax and net worked out as the sheet does
    assert row.entered_by is not None and row.underwriter == "KENYA ALLIANCE"

    page = (await client.get(f"{S}?source=manual", headers=_auth(token))).json()
    assert page["total"] == 1 and page["items"][0]["source"] == "manual"
    assert (await client.get(f"{S}/record/recent", headers=_auth(token))).json()[0]["policy_number"] == "ABC/999"
    export = await client.get("/api/v1/admin/sales-import/export?years=2026", headers=_auth(token))
    assert export.status_code == 200  # it is in the weekly report the system exports


async def test_a_sale_goes_on_an_existing_customer(client, db_session):
    from app.models.customer import Customer

    token = await _admin(client, db_session)
    provider = await _provider(db_session, "Kenya Alliance Insurance")
    existing = Customer(full_name="Peter K", phone="+254733000222")
    db_session.add(existing)
    await db_session.commit()
    by_phone = (await client.post(f"{S}/record", json=_sale(provider.id, phone="0733 000 222", policy_number="P/1"), headers=_auth(token))).json()
    assert by_phone["customer_id"] == str(existing.id) and by_phone["customer_existed"] is True
    chosen = (await client.post(f"{S}/record", json=_sale(provider.id, policy_number="P/2", customer_id=str(existing.id), premium="9000"), headers=_auth(token))).json()
    assert chosen["customer_id"] == str(existing.id)
    history = (await client.get(f"{S}/customers/{existing.id}/history", headers=_auth(token))).json()
    assert len(history["entries"]) == 2


async def test_bad_input_is_refused_with_a_reason_and_only_staff_can_record(client, db_session):
    token = await _admin(client, db_session)
    provider = await _provider(db_session, "Kenya Alliance Insurance")
    assert (await client.post(f"{S}/record", json=_sale(provider.id, premium="0"), headers=_auth(token))).status_code == 422
    assert (await client.post(f"{S}/record", json=_sale(provider.id, reg_or_product=""), headers=_auth(token))).status_code == 422
    backwards = await client.post(f"{S}/record", json=_sale(provider.id, expiry_date="2026-01-01"), headers=_auth(token))
    assert backwards.status_code == 400 and "after the start" in backwards.json()["detail"]
    bad_phone = await client.post(f"{S}/record", json=_sale(provider.id, phone="12345"), headers=_auth(token))
    assert bad_phone.status_code == 400
    no_insurer = await client.post(f"{S}/record", json={k: v for k, v in _sale(provider.id).items() if k != "provider_id"}, headers=_auth(token))
    assert no_insurer.status_code == 400

    customer_token = await _make_user(client, db_session, "buyer@example.com", "supersecret1", "customer")
    assert (await client.post(f"{S}/record", json=_sale(provider.id), headers=_auth(customer_token))).status_code == 403
    agent_token = await _make_user(client, db_session, "agent@example.com", "supersecret1", "sales_agent")
    assert (await client.post(f"{S}/record", json=_sale(provider.id), headers=_auth(agent_token))).status_code == 200  # agents can record
    assert (await client.delete(f"{S}/record/{uuid.uuid4()}", headers=_auth(agent_token))).status_code == 403  # but not void


async def test_a_new_insurer_can_be_added_from_the_form(client, db_session):
    from app.models.provider import InsuranceProvider

    token = await _admin(client, db_session)
    body = {k: v for k, v in _sale(uuid.uuid4()).items() if k != "provider_id"}
    res = await client.post(f"{S}/record", json={**body, "new_underwriter": "brand new insurer"}, headers=_auth(token))
    assert res.status_code == 200, res.text
    created = await db_session.scalar(select(InsuranceProvider).where(InsuranceProvider.name == "Brand New Insurer"))
    assert created.status == "inactive"  # never receives quote requests


async def test_double_entry_is_caught_unless_confirmed(client, db_session):
    from app.models.policy import Policy

    token = await _admin(client, db_session)
    provider = await _provider(db_session, "Kenya Alliance Insurance")
    assert (await client.post(f"{S}/record", json=_sale(provider.id), headers=_auth(token))).json()["created"] is True
    again = (await client.post(f"{S}/record", json=_sale(provider.id), headers=_auth(token))).json()
    assert again["created"] is False and again["duplicates"]
    assert await _count(db_session, Policy) == 1  # nothing was saved
    confirmed = (await client.post(f"{S}/record", json=_sale(provider.id, confirm_duplicate=True), headers=_auth(token))).json()
    assert confirmed["created"] is True and confirmed["policy_number"] == "ABC/999-2026"  # the number was in use, so the year was added
    assert any(f["code"] == "policy_number_year_added" for f in confirmed["flags"])


async def test_a_sale_typed_here_and_later_in_the_sheet_is_one_sale(client, db_session):
    from app.models.sales_ledger import SalesEntry

    token = await _admin(client, db_session)
    await _provider(db_session, "Monarch Insurance Company")
    provider = await _provider(db_session, "Kenya Alliance Insurance")
    await client.post(f"{S}/record", json=_sale(provider.id), headers=_auth(token))

    report = (await _upload(client, token, build_workbook(), dry_run=False)).json()
    assert report["counts"]["sales"]["new"] == 2 and report["counts"]["sales"]["unchanged"] == 1  # PETER KAMAU merged, not duplicated
    assert await _count(db_session, SalesEntry) == 3
    peter = await db_session.scalar(select(SalesEntry).where(SalesEntry.client_name == "PETER KAMAU"))
    assert peter.origin == "manual" and peter.posted_at is not None

    # a sale recorded here is never "missing from the sheet" just because the sheet does not have it
    without = (await _upload(client, token, build_workbook(include_february=False), dry_run=False)).json()
    assert without["counts"]["sales"]["missing"] == 0


async def test_a_sale_recorded_by_mistake_can_be_voided(client, db_session):
    from app.models.customer import Customer
    from app.models.policy import Policy
    from app.models.sales_ledger import SalesEntry

    token = await _admin(client, db_session)
    provider = await _provider(db_session, "Kenya Alliance Insurance")
    baseline = await _count(db_session, Customer)
    made = (await client.post(f"{S}/record", json=_sale(provider.id), headers=_auth(token))).json()
    entry_id = made["entry_id"]
    done = await client.delete(f"{S}/record/{entry_id}", headers=_auth(token))
    assert done.status_code == 200 and done.json()["voided"] is True
    db_session.expire_all()
    assert await _count(db_session, Policy) == 0 and await _count(db_session, SalesEntry) == 0
    assert await _count(db_session, Customer) == baseline  # the customer created for it went too

    await _upload(client, token, build_workbook(), dry_run=False)
    workbook_row = await db_session.scalar(select(SalesEntry.id).limit(1))
    assert (await client.delete(f"{S}/record/{workbook_row}", headers=_auth(token))).status_code == 404  # sheet rows are fixed in the sheet


async def test_posted_policies_keep_their_renewal_follow_up(client, db_session):
    from app.models.policy import Policy
    from app.models.sales_ledger import SalesEntry

    token = await _admin(client, db_session)
    await _provider(db_session, "Monarch Insurance Company")
    await _upload(client, token, build_workbook(), dry_run=False)
    await _link_everyone(client, token)
    await client.post(f"{P}/run?dry_run=false", headers=_auth(token))
    soon = date.today() + timedelta(days=10)
    await db_session.execute(update(Policy).where(Policy.policy_number == "123456").values(end_date=soon))
    await db_session.execute(update(SalesEntry).where(SalesEntry.policy_number == "123456").values(expiry_date=soon))
    await db_session.commit()

    page = (await client.get(f"{S}/renewals?days=30", headers=_auth(token))).json()
    assert [(i["client_name"], i["source"]) for i in page["items"]] == [("JOHN DOE", "workbook")]  # listed once, from the ledger
    saved = await client.put(f"{S}/renewals/{page['items'][0]['id']}", json={"status": "contacted", "note": "call Monday"}, headers=_auth(token))
    assert saved.status_code == 200
    assert (await client.get(f"{S}/renewals?days=30&status=contacted", headers=_auth(token))).json()["total"] == 1
