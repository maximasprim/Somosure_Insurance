"""Platform and workbook data read together: all sales, renewals, customers, the dashboard and search."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select, update

from tests.sales_import_fixtures import build_workbook
from tests.test_sales_import_api import _admin, _auth, _make_user, _upload

SALES = "/api/v1/admin/sales"


async def _seed_policy(db_session, provider, number, premium, *, is_mock=False, phone="0711000111", name="Platform Buyer", end_date=None):
    from app.models.application import Application
    from app.models.customer import Customer
    from app.models.policy import Policy
    from app.models.quote import Quote, QuoteRequest

    customer = Customer(full_name=name, phone=phone)
    db_session.add(customer)
    await db_session.flush()
    ref = uuid.uuid4().hex[:8].upper()
    qr = QuoteRequest(reference=f"SOM-2026-{ref}", customer_id=customer.id, category="motor", status="quoted")
    db_session.add(qr)
    await db_session.flush()
    quote = Quote(quote_request_id=qr.id, provider_id=provider.id, premium=Decimal(premium), taxes=Decimal("0"), fees=Decimal("0"), total=Decimal(premium), is_mock=is_mock, status="selected")
    db_session.add(quote)
    await db_session.flush()
    application = Application(reference=f"SOM-APP-2026-{ref}", quote_id=quote.id, customer_id=customer.id, status="approved")
    db_session.add(application)
    await db_session.flush()
    policy = Policy(
        policy_number=number, application_id=application.id, provider_id=provider.id, customer_id=customer.id,
        start_date=date.today(), end_date=end_date or date(date.today().year + 1, 1, 1), premium=Decimal(premium),
        status="active", is_mock=is_mock,
    )
    db_session.add(policy)
    await db_session.commit()
    return customer, policy


async def test_staff_only(client, db_session):
    token = await _make_user(client, db_session, "cust2@example.com", "supersecret1", "customer")
    assert (await client.get(SALES, headers=_auth(token))).status_code == 403
    assert (await client.get(f"{SALES}/renewals", headers=_auth(token))).status_code == 403
    assert (await client.get(SALES)).status_code in (401, 403)


async def test_all_sales_counts_each_sale_once_across_both_sources(client, db_session, seeded_providers):
    token = await _admin(client, db_session)
    await _seed_policy(db_session, seeded_providers[0], "PLAT-1", "20000", name="Online Buyer")
    await _seed_policy(db_session, seeded_providers[0], "DEMO-1", "99999", is_mock=True, phone="0711000222", name="Demo Buyer")
    # also sold on the platform AND written in the sheet (same policy number as JOHN DOE's row)
    await _seed_policy(db_session, seeded_providers[0], "123456", "50000", phone="0711000333", name="John Doe")
    await _upload(client, token, build_workbook(), dry_run=False)

    page = (await client.get(SALES, headers=_auth(token))).json()
    by_source = {}
    for item in page["items"]:
        by_source.setdefault(item["source"], []).append(item["policy_number"])
    # 3 workbook rows (one of them is also a platform policy) + 1 platform-only; the demo policy is not counted
    assert page["total"] == 4
    assert by_source["platform"] == ["PLAT-1"]
    assert "123456" in by_source["platform+workbook"] and len(by_source["workbook"]) == 2
    assert all(i["policy_number"] != "DEMO-1" for i in page["items"])

    only_platform = (await client.get(f"{SALES}?source=platform", headers=_auth(token))).json()
    assert only_platform["total"] == 1
    only_workbook = (await client.get(f"{SALES}?source=workbook", headers=_auth(token))).json()
    assert only_workbook["total"] == 3
    options = (await client.get(f"{SALES}/options", headers=_auth(token))).json()
    assert "MONARCH" in options["underwriters"] and "HQ" in options["branches"]


async def test_import_links_workbook_policies_and_claims_to_the_customer_who_bought_on_the_platform(client, db_session, seeded_providers):
    token = await _admin(client, db_session)
    customer, _ = await _seed_policy(db_session, seeded_providers[0], "123456", "50000", phone="0711000333", name="John Doe")
    report = (await _upload(client, token, build_workbook(), dry_run=False)).json()
    assert report["customer_links"]["linked_by_policy"] == 1

    history = (await client.get(f"{SALES}/customers/{customer.id}/history", headers=_auth(token))).json()
    assert [e["client_name"] for e in history["entries"]] == ["JOHN DOE"]
    assert [c["client_name"] for c in history["claims"]] == ["JOHN DOE"]  # the claim follows the sale it belongs to


async def test_a_phone_number_added_here_matches_the_customer_and_survives_re_uploads(client, db_session):
    from app.models.customer import Customer

    token = await _admin(client, db_session)
    existing = Customer(full_name="Peter K", phone="+254733000222")
    db_session.add(existing)
    await db_session.commit()
    data = build_workbook()
    await _upload(client, token, data, dry_run=False)

    waiting = (await client.get(f"{SALES}/customers/needs-phone?q=PETER", headers=_auth(token))).json()
    assert waiting["total"] == 1 and waiting["items"][0]["client_name"] == "PETER KAMAU"
    bad = await client.post(f"{SALES}/customers/phone", json={"client_key": "PETER KAMAU", "phone": "12345678"}, headers=_auth(token))
    assert bad.status_code == 400
    ok = await client.post(f"{SALES}/customers/phone", json={"client_key": "PETER KAMAU", "phone": "0733 000 222"}, headers=_auth(token))
    assert ok.status_code == 200 and ok.json()["rows"] == 1

    history = (await client.get(f"{SALES}/customers/{existing.id}/history", headers=_auth(token))).json()
    assert [e["client_name"] for e in history["entries"]] == ["PETER KAMAU"]  # matched on the phone number

    again = (await _upload(client, token, data, dry_run=False)).json()
    assert again["counts"]["sales"]["updated"] == 0  # the sheet still has no phone; the number added here is kept
    row = (await client.get(f"/api/v1/admin/sales-import/entries?q=PETER", headers=_auth(token))).json()["items"][0]
    assert row["phone"] == "+254733000222"


async def test_customers_are_only_created_when_asked_and_after_a_dry_run(client, db_session):
    from app.models.customer import Customer

    token = await _admin(client, db_session)
    await _upload(client, token, build_workbook(), dry_run=False)
    await client.post(f"{SALES}/customers/phone", json={"client_key": "JANE ROE", "phone": "0700111222"}, headers=_auth(token))
    before = len((await db_session.scalars(select(Customer))).all())

    dry = (await client.post(f"{SALES}/customers/link?create=true&dry_run=true", headers=_auth(token))).json()
    assert dry["customers_created"] == 1
    assert len((await db_session.scalars(select(Customer))).all()) == before  # a dry run writes nothing

    no_create = (await client.post(f"{SALES}/customers/link?create=false&dry_run=false", headers=_auth(token))).json()
    assert no_create["customers_created"] == 0
    assert len((await db_session.scalars(select(Customer))).all()) == before

    done = (await client.post(f"{SALES}/customers/link?create=true&dry_run=false", headers=_auth(token))).json()
    assert done["customers_created"] == 1
    created = await db_session.scalar(select(Customer).where(Customer.phone == "+254700111222"))
    assert created is not None and created.lead_source == "workbook" and created.consent_marketing is False
    status = (await client.get(f"{SALES}/customers/status", headers=_auth(token))).json()
    assert status["linked"] == 1 and status["clients"] == 3

    # clients with no phone are never created
    assert done["clients_without_phone"] == 2


async def test_renewals_worklist_covers_both_sources_and_remembers_follow_up(client, db_session, seeded_providers):
    from app.models.sales_ledger import SalesEntry

    token = await _admin(client, db_session)
    soon = date.today() + timedelta(days=10)
    await _seed_policy(db_session, seeded_providers[0], "PLAT-RENEW", "15000", name="Online Renewer", end_date=soon)
    await _upload(client, token, build_workbook(), dry_run=False)
    await db_session.execute(update(SalesEntry).where(SalesEntry.client_name == "JOHN DOE").values(expiry_date=soon))
    await db_session.commit()

    page = (await client.get(f"{SALES}/renewals?days=30", headers=_auth(token))).json()
    sources = {i["client_name"]: i["source"] for i in page["items"]}
    assert sources == {"Online Renewer": "platform", "JOHN DOE": "workbook"}
    john = next(i for i in page["items"] if i["client_name"] == "JOHN DOE")
    assert john["status"] == "due" and john["days_left"] == 10

    saved = await client.put(f"{SALES}/renewals/{john['id']}", json={"status": "contacted", "note": "call back Friday"}, headers=_auth(token))
    assert saved.status_code == 200
    again = (await client.get(f"{SALES}/renewals?days=30&source=workbook", headers=_auth(token))).json()
    assert again["items"][0]["status"] == "contacted" and again["items"][0]["note"] == "call back Friday"

    # a re-upload of the sheet never wipes the follow-up (the sheet's own expiry date does come back, as the sheet is the truth)
    await _upload(client, token, build_workbook(), dry_run=False)
    kept = (await db_session.execute(select(SalesEntry.follow_up_status, SalesEntry.follow_up_note).where(SalesEntry.client_name == "JOHN DOE"))).one()
    assert tuple(kept) == ("contacted", "call back Friday")

    await db_session.execute(update(SalesEntry).where(SalesEntry.client_name == "JOHN DOE").values(expiry_date=soon))
    await db_session.commit()
    await client.put(f"{SALES}/renewals/{john['id']}", json={"status": "renewed"}, headers=_auth(token))
    assert (await client.get(f"{SALES}/renewals?days=30&source=workbook", headers=_auth(token))).json()["total"] == 0
    assert (await client.get(f"{SALES}/renewals?days=30&source=workbook&include_closed=true", headers=_auth(token))).json()["total"] == 1
    bad = await client.put(f"{SALES}/renewals/{john['id']}", json={"status": "nonsense"}, headers=_auth(token))
    assert bad.status_code == 422


async def test_dashboard_gets_an_all_sales_section_and_keeps_everything_else(client, db_session):
    token = await _admin(client, db_session)
    await _upload(client, token, build_workbook(), dry_run=False)
    res = await client.get("/api/v1/admin/reports/analytics?days=365", headers=_auth(token))
    assert res.status_code == 200
    body = res.json()
    for key in ("kpis", "snapshot", "trend", "funnel", "providers", "policies_by_source", "unavailable"):
        assert key in body  # nothing that was there has gone
    assert "workbook" not in body["unavailable"]
    section = body["workbook"]
    assert set(section) >= {"kpis", "monthly", "by_underwriter", "by_branch", "by_staff", "renewals", "customers", "coverage"}
    assert section["customers"]["workbook_clients"] == 3


async def test_global_search_also_finds_workbook_policies(client, db_session):
    token = await _admin(client, db_session)
    await _upload(client, token, build_workbook(), dry_run=False)
    res = await client.get("/api/v1/admin/search", params={"q": "KDR904V"}, headers=_auth(token))
    assert res.status_code == 200
    body = res.json()
    assert [w["client_name"] for w in body["workbook"]] == ["JOHN DOE"]
    for key in ("customers", "quotes", "policies", "claims", "applications", "payments"):
        assert key in body
