"""Posting the workbook into the system's own tables, linking underwriters to providers, keeping in step, undoing."""

import uuid
from datetime import date, timedelta

from sqlalchemy import func, select, update

from tests.sales_import_fixtures import build_workbook
from tests.test_sales_import_api import _admin, _auth, _upload
from tests.test_sales_sync_api import _seed_policy

P = "/api/v1/admin/sales-import/posting"


async def _provider(db_session, name):
    from app.models.provider import InsuranceProvider

    provider = InsuranceProvider(id=uuid.uuid4(), name=name, provider_type="insurer", integration_mode="mock", status="active")
    db_session.add(provider)
    await db_session.commit()
    return provider


async def _count(db_session, model, *where):
    return await db_session.scalar(select(func.count()).select_from(model).where(*where))


async def _link_everyone(client, token):
    """Link the sheet's other underwriters by creating inactive providers for them."""
    for name in ("DIRECT LINE", "KENYA ALLIANCE"):
        res = await client.put(f"{P}/underwriters", json={"underwriter": name, "create_new": True}, headers=_auth(token))
        assert res.status_code == 200, res.text


async def test_underwriters_in_the_sheet_are_linked_to_providers_already_in_the_system(client, db_session):
    from app.models.provider import InsuranceProvider

    token = await _admin(client, db_session)
    monarch = await _provider(db_session, "Monarch Insurance Company")
    await _upload(client, token, build_workbook(), dry_run=False)

    overview = (await client.get(f"{P}/underwriters", headers=_auth(token))).json()
    by_name = {u["underwriter"]: u for u in overview["underwriters"]}
    assert by_name["MONARCH"]["provider_id"] == str(monarch.id) and by_name["MONARCH"]["linked"] is True  # recognised as the same insurer
    assert by_name["DIRECT LINE"]["provider_id"] is None

    status = (await client.get(f"{P}/status", headers=_auth(token))).json()
    assert status["ready"] == 1 and status["held"] == {"no_provider_link": 2}
    assert {u["underwriter"] for u in status["unlinked_underwriters"]} == {"DIRECT LINE", "KENYA ALLIANCE"}

    await _link_everyone(client, token)
    created = await db_session.scalar(select(InsuranceProvider).where(InsuranceProvider.name == "Direct Line"))
    assert created.status == "inactive"  # never receives quote requests
    assert (await client.get(f"{P}/status", headers=_auth(token))).json()["ready"] == 3

    # pointing an underwriter at an existing provider instead
    other = await _provider(db_session, "Kenya Alliance Insurance")
    res = await client.put(f"{P}/underwriters", json={"underwriter": "KENYA ALLIANCE", "provider_id": str(other.id)}, headers=_auth(token))
    assert res.status_code == 200
    assert (await client.put(f"{P}/underwriters", json={"underwriter": "X"}, headers=_auth(token))).status_code == 400


async def test_posting_creates_the_whole_chain_and_the_rest_of_the_system_sees_it(client, db_session):
    from app.models.application import Application
    from app.models.customer import Customer
    from app.models.payment import Payment
    from app.models.policy import Policy, PolicyEvent
    from app.models.quote import Quote, QuoteRequest

    token = await _admin(client, db_session)
    await _provider(db_session, "Monarch Insurance Company")
    await _upload(client, token, build_workbook(), dry_run=False)
    await _link_everyone(client, token)
    baseline_customers = await _count(db_session, Customer)

    preview = (await client.post(f"{P}/run?dry_run=true", headers=_auth(token))).json()
    assert preview["to_post"] == 3 and await _count(db_session, Policy) == 0  # a preview writes nothing

    done = (await client.post(f"{P}/run?dry_run=false", headers=_auth(token))).json()
    assert done["posted"] == 3 and done["customers_created"] == 3
    for model in (Policy, Application, Quote, QuoteRequest, Payment):
        assert await _count(db_session, model) == 3
    assert await _count(db_session, Customer) == baseline_customers + 3

    john = await db_session.scalar(select(Policy).where(Policy.policy_number == "123456"))
    assert john.source == "workbook" and john.is_mock is False and john.payment_status == "paid" and john.status in ("active", "expired")
    assert (john.start_date, john.end_date) == (date(2026, 1, 6), date(2027, 1, 5)) and john.premium == 50000 and john.commission == 5000
    assert john.created_at.date() == date(2026, 1, 7)  # dated by the sale, so the dashboard does not see an import-day spike
    payment = await db_session.scalar(select(Payment).where(Payment.policy_id == john.id))
    assert (payment.method, payment.status, payment.amount) == ("offline", "successful", 50000) and payment.created_at.date() == date(2026, 1, 7)
    quote = await db_session.scalar(select(Quote).join(Application, Application.quote_id == Quote.id).where(Application.id == john.application_id))
    assert quote.is_mock is False and quote.status == "selected" and quote.total == 50000
    assert await _count(db_session, PolicyEvent, PolicyEvent.policy_id == john.id, PolicyEvent.event_type == "imported") == 1
    customer = await db_session.get(Customer, john.customer_id)
    assert customer.lead_source == "workbook" and customer.phone == "" and customer.consent_marketing is False

    # flagged for review, not refused
    review = (await client.get(f"{P}/review?code=customer_no_phone", headers=_auth(token))).json()
    assert review["total"] == 3
    # visible to the pages that already existed
    found = (await client.get("/api/v1/admin/search", params={"q": "123456"}, headers=_auth(token))).json()
    assert [p["policy_number"] for p in found["policies"]] == ["123456"]
    # and counted once in the combined sales list
    page = (await client.get("/api/v1/admin/sales?source=workbook", headers=_auth(token))).json()
    assert page["total"] == 3
    assert (await client.get("/api/v1/admin/sales?source=platform", headers=_auth(token))).json()["total"] == 0


async def test_posting_twice_changes_nothing_and_later_sheet_changes_flow_through(client, db_session):
    from app.models.payment import Payment
    from app.models.policy import Policy

    token = await _admin(client, db_session)
    await _provider(db_session, "Monarch Insurance Company")
    await _upload(client, token, build_workbook(), dry_run=False)
    await _link_everyone(client, token)
    await client.post(f"{P}/run?dry_run=false", headers=_auth(token))
    again = (await client.post(f"{P}/run?dry_run=false", headers=_auth(token))).json()
    assert again["posted"] == 0 and await _count(db_session, Policy) == 3

    report = (await _upload(client, token, build_workbook(premium_jan=51000), dry_run=False)).json()
    assert report["posting"]["resynced"]["policies"] == 1
    db_session.expire_all()
    john = await db_session.scalar(select(Policy).where(Policy.policy_number == "123456"))
    assert john.premium == 51000 and john.commission == 5100
    assert (await db_session.scalar(select(Payment.amount).where(Payment.policy_id == john.id))) == 51000

    # importing with "post" also appends rows that are new in the sheet
    more = (await _upload(client, token, build_workbook(premium_jan=51000, include_year_typo=True), dry_run=False, query="&post=true")).json()
    assert more["posting"]["posted"]["posted"] == 1 and await _count(db_session, Policy) == 4


async def test_rows_the_system_cannot_store_are_held_and_reported_not_dropped(client, db_session):
    token = await _admin(client, db_session)
    await _provider(db_session, "Monarch Insurance Company")
    await _upload(client, token, build_workbook(include_no_premium=True), dry_run=False)
    held = (await client.get(f"{P}/held?reason=missing_premium", headers=_auth(token))).json()
    assert [i["client_name"] for i in held["items"]] == ["NO PREMIUM"]
    assert held["items"][0]["reasons"][0]["code"] == "missing_premium"
    # still in the ledger and in the combined sales list, awaiting a fix in the sheet
    assert (await client.get("/api/v1/admin/sales?q=NO PREMIUM", headers=_auth(token))).json()["total"] == 1


async def test_a_phone_added_later_reaches_the_posted_customer(client, db_session):
    from app.models.customer import Customer

    token = await _admin(client, db_session)
    await _provider(db_session, "Monarch Insurance Company")
    await _upload(client, token, build_workbook(), dry_run=False)
    await _link_everyone(client, token)
    await client.post(f"{P}/run?dry_run=false", headers=_auth(token))
    res = await client.post("/api/v1/admin/sales/customers/phone", json={"client_key": "JANE ROE", "phone": "0700111222"}, headers=_auth(token))
    assert res.status_code == 200
    jane = await db_session.scalar(select(Customer).where(Customer.full_name == "Jane Roe"))
    await db_session.refresh(jane)
    assert jane.phone == "+254700111222"


async def test_workbook_policies_are_not_reminded_automatically_until_switched_on(client, db_session):
    from app.models.policy import Policy
    from app.services.renewal_service import scan_renewals

    token = await _admin(client, db_session)
    await _provider(db_session, "Monarch Insurance Company")
    await _upload(client, token, build_workbook(), dry_run=False)
    await _link_everyone(client, token)
    await client.post(f"{P}/run?dry_run=false", headers=_auth(token))
    await db_session.execute(update(Policy).values(end_date=date.today() + timedelta(days=30), status="active"))
    await db_session.commit()
    result = await scan_renewals(db_session)
    assert result["reminders_sent"] == 0  # all three are workbook policies


async def test_undoing_a_posting_removes_only_what_it_created(client, db_session, seeded_providers):
    from app.models.customer import Customer
    from app.models.payment import Payment
    from app.models.policy import Policy
    from app.models.sales_ledger import SalesEntry

    token = await _admin(client, db_session)
    await _seed_policy(db_session, seeded_providers[0], "PLAT-KEEP", "20000", name="Platform Buyer")
    await _provider(db_session, "Monarch Insurance Company")
    await _upload(client, token, build_workbook(), dry_run=False)
    await _link_everyone(client, token)
    await client.post(f"{P}/run?dry_run=false", headers=_auth(token))
    assert await _count(db_session, Policy) == 4

    preview = (await client.post(f"{P}/unpost?dry_run=true", headers=_auth(token))).json()
    assert preview["policies"] == 3 and await _count(db_session, Policy) == 4

    other = await _make_non_super_admin(client, db_session)
    assert (await client.post(f"{P}/unpost?dry_run=false", headers=_auth(other))).status_code == 403

    done = (await client.post(f"{P}/unpost?dry_run=false", headers=_auth(token))).json()
    assert done["policies_removed"] == 3 and done["policies_kept"] == 0
    db_session.expire_all()
    remaining = (await db_session.scalars(select(Policy.policy_number))).all()
    assert remaining == ["PLAT-KEEP"]  # the platform's own policy is untouched
    assert await _count(db_session, Payment) == 1
    assert await db_session.scalar(select(Customer).where(Customer.full_name == "Platform Buyer")) is not None
    assert await _count(db_session, Customer, Customer.lead_source == "workbook") == 0
    # the ledger keeps its rows, ready to post again
    assert await _count(db_session, SalesEntry, SalesEntry.posted_at.is_(None)) == 3


async def _make_non_super_admin(client, db_session):
    from tests.test_sales_import_api import _make_user

    return await _make_user(client, db_session, "mgr@example.com", "supersecret1", "management")


async def test_the_post_tab_can_load_in_one_call(client, db_session):
    token = await _admin(client, db_session)
    await _provider(db_session, "Monarch Insurance Company")
    await _upload(client, token, build_workbook(include_no_premium=True), dry_run=False)
    one = (await client.get(f"{P}/overview?reason=missing_premium", headers=_auth(token))).json()
    assert set(one) == {"status", "held", "review", "underwriters"}
    assert one["status"] == (await client.get(f"{P}/status", headers=_auth(token))).json()
    assert [i["client_name"] for i in one["held"]["items"]] == ["NO PREMIUM"]
    assert {u["underwriter"] for u in one["underwriters"]["underwriters"]} >= {"MONARCH", "DIRECT LINE"}
