"""Comprehensive cover without a valuation report: optional document, one-month sticker, valuation pending."""

import io
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.services.motor_terms import add_months
from tests.test_sales_import_api import _admin, _auth, _make_user

PDF = b"%PDF-1.4 fake pdf content"


@pytest.fixture(autouse=True)
def demo_quotes_and_local_storage(tmp_path, monkeypatch):
    """Self-contained: mock insurers count as quotable, and uploaded documents go to a temp folder rather than to
    whatever storage the project's .env points at (which on a developer machine can be the live bucket), and payments
    are simulated."""
    from app.core.config import get_settings
    from app.core.storage import LocalDiskStorage
    from app.services import application_service

    monkeypatch.setattr(get_settings(), "allow_demo_quote_categories", True)
    monkeypatch.setattr(get_settings(), "mpesa_mode", "mock")  # never call the real M-Pesa API, whatever .env holds
    storage = LocalDiskStorage(str(tmp_path / "documents"))
    monkeypatch.setattr(application_service, "get_storage", lambda: storage)


async def _upload(client, application_id, doc_type):
    return await client.post(
        f"/api/v1/applications/{application_id}/documents",
        params={"document_type": doc_type},
        files={"file": (f"{doc_type}.pdf", io.BytesIO(PDF), "application/pdf")},
    )


async def _apply(client, db_session, *, phone, cover="comprehensive", reg="KDA 123X", valuation=False, submit=True):
    """Quote -> application -> documents (-> submit). Returns (quote, application_id, submit_response)."""
    from app.models.customer import Customer

    res = await client.post(
        "/api/v1/quotes",
        json={"category": "motor", "answers": {"owner_phone": phone, "owner_name": "Prov Test", "cover_type": cover, "registration_number": reg}},
    )
    assert res.status_code == 200, res.text
    quote = res.json()["quotes"][0]
    customer = await db_session.scalar(select(Customer).where(Customer.phone == phone))
    created = await client.post("/api/v1/applications", json={"quote_id": quote["id"], "customer_id": str(customer.id), "applicant_details": {}})
    assert created.status_code == 200, created.text
    application_id = created.json()["id"]
    for doc_type in ("national_id", "logbook", "kra_pin"):
        assert (await _upload(client, application_id, doc_type)).status_code == 200
    if valuation:
        assert (await _upload(client, application_id, "valuation_report")).status_code == 200
    submitted = await client.post(f"/api/v1/applications/{application_id}/submit") if submit else None
    return quote, str(customer.id), application_id, submitted


async def _pay(client, db_session, quote, customer_id, application_id):
    from app.services.application_service import approve_application

    await approve_application(db_session, application_id)
    pay = await client.post(
        "/api/v1/payments/initiate",
        json={"application_id": application_id, "customer_id": customer_id, "amount": quote["total"], "phone": "0700000001", "method": "mpesa"},
    )
    assert pay.status_code == 200, pay.text
    done = await client.post(
        f"/api/v1/payments/{pay.json()['provider_transaction_id']}/simulate-completion",
        params={"outcome": "successful", "amount": quote["total"]},
    )
    assert done.json()["status"] == "successful"
    from app.automation.engine import run_due_automations
    from app.models.policy import Policy

    await run_due_automations(db_session)  # automation runs are scheduled, not inline: this is what issues the sticker
    db_session.expire_all()
    return await db_session.scalar(select(Policy).where(Policy.application_id == application_id))


async def _stickers(db_session, policy):
    from app.models.sticker import Sticker

    return (await db_session.scalars(select(Sticker).where(Sticker.policy_id == policy.id))).all()


# ------------------------------------------------------------------------------------ the checklist


async def test_the_valuation_report_is_optional_but_the_rest_still_required(client, db_session, seeded_providers):
    res = await client.post("/api/v1/quotes", json={"category": "motor", "answers": {"owner_phone": "0700000011", "owner_name": "Chk", "cover_type": "comprehensive"}})
    from app.models.customer import Customer

    customer = await db_session.scalar(select(Customer).where(Customer.phone == "0700000011"))
    app = (await client.post("/api/v1/applications", json={"quote_id": res.json()["quotes"][0]["id"], "customer_id": str(customer.id), "applicant_details": {}})).json()

    first = (await client.post(f"/api/v1/applications/{app['id']}/documents/prepare")).json()
    by_type = {i["type"]: i for i in first["items"]}
    assert by_type["valuation_report"]["optional"] is True and by_type["national_id"]["optional"] is False
    assert sorted(first["missing"]) == ["kra_pin", "logbook", "national_id"]  # the valuation report is NOT a required missing item
    assert first["optional_missing"] == ["valuation_report"] and first["complete"] is False

    for doc_type in ("national_id", "logbook", "kra_pin"):
        await _upload(client, app["id"], doc_type)
    second = (await client.get(f"/api/v1/applications/{app['id']}/documents/checklist")).json()
    assert second["complete"] is True and second["missing"] == [] and second["optional_missing"] == ["valuation_report"]

    await _upload(client, app["id"], "valuation_report")
    third = (await client.get(f"/api/v1/applications/{app['id']}/documents/checklist")).json()
    assert third["complete"] is True and third["optional_missing"] == []


async def test_the_quote_page_lists_it_as_optional_for_comprehensive_only(client):
    comp = (await client.get("/api/v1/quotes/document-requirements?category=motor&cover_type=comprehensive")).json()["insurance"]
    valuation = next(d for d in comp if d["type"] == "valuation_report")
    assert valuation["optional"] is True and "one-month" in valuation["description"]
    assert all(d["optional"] is False for d in comp if d["type"] != "valuation_report")

    tpo = (await client.get("/api/v1/quotes/document-requirements?category=motor&cover_type=tpo")).json()["insurance"]
    assert "valuation_report" not in {d["type"] for d in tpo}


# ------------------------------------------------------------------------------------ issuing the policy


async def test_without_a_report_the_customer_pays_the_quote_and_gets_a_one_month_sticker(client, db_session, seeded_providers, seeded_automation_rules):
    quote, customer_id, application_id, submitted = await _apply(client, db_session, phone="0700000021")
    assert submitted.status_code == 200  # submitting without the valuation report is allowed

    policy = await _pay(client, db_session, quote, customer_id, application_id)
    today = date.today()
    last_day = add_months(today, 1) - timedelta(days=1)

    assert policy.status == "active" and float(policy.premium) == float(quote["premium"])  # the premium is what was quoted: nothing repriced
    assert policy.end_date == today + timedelta(days=365)  # the policy is still the annual one
    assert policy.valuation_pending is True and policy.valuation_due == last_day and policy.provisional_vehicle == "KDA123X"

    stickers = await _stickers(db_session, policy)
    assert len(stickers) == 1 and (stickers[0].valid_from, stickers[0].valid_to) == (today, last_day)  # ONE month, not the whole term

    from app.models.policy import PolicyEvent

    event = await db_session.scalar(select(PolicyEvent).where(PolicyEvent.policy_id == policy.id))
    assert event.metadata_json["provisional"] is True


async def test_with_a_report_nothing_changes(client, db_session, seeded_providers, seeded_automation_rules):
    quote, customer_id, application_id, submitted = await _apply(client, db_session, phone="0700000022", valuation=True)
    assert submitted.status_code == 200
    policy = await _pay(client, db_session, quote, customer_id, application_id)

    assert policy.valuation_pending is False and policy.valuation_due is None and policy.provisional_vehicle is None
    stickers = await _stickers(db_session, policy)
    assert len(stickers) == 1 and (stickers[0].valid_from, stickers[0].valid_to) == (None, None)  # covers the whole policy term, as before


async def test_a_rejected_report_does_not_count(client, db_session, seeded_providers, seeded_automation_rules):
    from app.models.application import ApplicationDocument

    quote, customer_id, application_id, _ = await _apply(client, db_session, phone="0700000023", valuation=True)
    await db_session.execute(
        ApplicationDocument.__table__.update().where(ApplicationDocument.document_type == "valuation_report").values(status="rejected")
    )
    await db_session.commit()
    policy = await _pay(client, db_session, quote, customer_id, application_id)
    assert policy.valuation_pending is True


async def test_third_party_cover_is_never_provisional(client, db_session, seeded_providers, seeded_automation_rules):
    quote, customer_id, application_id, submitted = await _apply(client, db_session, phone="0700000024", cover="tpo")
    assert submitted.status_code == 200
    policy = await _pay(client, db_session, quote, customer_id, application_id)
    assert policy.valuation_pending is False
    stickers = await _stickers(db_session, policy)
    assert (stickers[0].valid_from, stickers[0].valid_to) == (None, None)


# ------------------------------------------------------------------------------------ the one-per-vehicle rule


async def test_a_vehicle_cannot_be_given_a_second_one_month_cover_while_the_first_waits(client, db_session, seeded_providers, seeded_automation_rules):
    quote, customer_id, application_id, _ = await _apply(client, db_session, phone="0700000031", reg="KDA 123X")
    first = await _pay(client, db_session, quote, customer_id, application_id)
    assert first.valuation_pending is True

    # the same car, typed differently, by someone else, again without a report: refused when they submit
    _, _, second_app, refused = await _apply(client, db_session, phone="0700000032", reg="kda123x")
    assert refused.status_code == 409
    assert "KDA123X" in refused.json()["detail"] and "valuation report" in refused.json()["detail"]

    # a different car is fine
    _, _, other_app, fine = await _apply(client, db_session, phone="0700000033", reg="KDB 456Y")
    assert fine.status_code == 200

    # the same car WITH the report is fine - that is the way out
    await _upload(client, second_app, "valuation_report")
    assert (await client.post(f"/api/v1/applications/{second_app}/submit")).status_code == 200


async def test_once_the_report_is_received_the_vehicle_is_free_again(client, db_session, seeded_providers, seeded_automation_rules):
    quote, customer_id, application_id, _ = await _apply(client, db_session, phone="0700000041", reg="KDC 789Z")
    policy = await _pay(client, db_session, quote, customer_id, application_id)
    admin = await _admin(client, db_session)
    assert (await client.post(f"/api/v1/admin/policies/{policy.id}/valuation-received", headers=_auth(admin))).status_code == 200

    _, _, _, again = await _apply(client, db_session, phone="0700000042", reg="KDC 789Z")
    assert again.status_code == 200


async def test_a_cancelled_one_month_cover_does_not_block_the_vehicle(client, db_session, seeded_providers, seeded_automation_rules):
    quote, customer_id, application_id, _ = await _apply(client, db_session, phone="0700000043", reg="KDD 111A")
    policy = await _pay(client, db_session, quote, customer_id, application_id)
    policy.status = "cancelled"
    await db_session.commit()
    _, _, _, again = await _apply(client, db_session, phone="0700000044", reg="KDD 111A")
    assert again.status_code == 200


# ------------------------------------------------------------------------------------ staff and customer views


async def test_staff_can_filter_and_clear_the_flag_and_it_changes_nothing_else(client, db_session, seeded_providers, seeded_automation_rules):
    quote, customer_id, application_id, _ = await _apply(client, db_session, phone="0700000051", reg="KDE 222B")
    pending = await _pay(client, db_session, quote, customer_id, application_id)
    # plain values, read straight away: objects expire whenever the next request commits
    pending_id, pending_number, pending_due, premium_before = pending.id, pending.policy_number, pending.valuation_due, float(pending.premium)
    q2, c2, a2, _ = await _apply(client, db_session, phone="0700000052", reg="KDF 333C", valuation=True)
    normal = await _pay(client, db_session, q2, c2, a2)
    normal_id, normal_number = normal.id, normal.policy_number

    admin = await _admin(client, db_session)
    listed = (await client.get("/api/v1/admin/policies?valuation_pending=true", headers=_auth(admin))).json()
    assert [p["policy_number"] for p in listed] == [pending_number]
    assert listed[0]["valuation_pending"] is True and listed[0]["valuation_due"] == pending_due.isoformat()
    everyone = (await client.get("/api/v1/admin/policies", headers=_auth(admin))).json()
    assert {p["policy_number"] for p in everyone} == {pending_number, normal_number}

    cleared = await client.post(f"/api/v1/admin/policies/{pending_id}/valuation-received", headers=_auth(admin))
    assert cleared.status_code == 200 and cleared.json()["valuation_pending"] is False
    db_session.expire_all()
    from app.models.policy import Policy, PolicyEvent

    after = await db_session.get(Policy, pending_id)
    assert after.valuation_pending is False and after.valuation_received_at is not None
    assert float(after.premium) == premium_before and len(await _stickers(db_session, after)) == 1  # no repricing, no extra sticker
    events = (await db_session.scalars(select(PolicyEvent.event_type).where(PolicyEvent.policy_id == pending_id))).all()
    assert "valuation_received" in events

    assert (await client.post(f"/api/v1/admin/policies/{pending_id}/valuation-received", headers=_auth(admin))).status_code == 409
    assert (await client.post(f"/api/v1/admin/policies/{normal_id}/valuation-received", headers=_auth(admin))).status_code == 409
    assert (await client.post("/api/v1/admin/policies/00000000-0000-0000-0000-000000000000/valuation-received", headers=_auth(admin))).status_code == 404

    customer = await _make_user(client, db_session, "cust@example.com", "supersecret1", "customer")
    assert (await client.post(f"/api/v1/admin/policies/{pending_id}/valuation-received", headers=_auth(customer))).status_code == 403


async def test_the_customer_policy_payload_carries_what_the_dashboard_needs(client, db_session, seeded_providers, seeded_automation_rules):
    from app.schemas.application import PolicyOut

    quote, customer_id, application_id, _ = await _apply(client, db_session, phone="0700000061", reg="KDG 444D")
    policy = await _pay(client, db_session, quote, customer_id, application_id)
    out = PolicyOut.model_validate(policy)
    assert out.valuation_pending is True and out.valuation_due == policy.valuation_due and str(out.application_id) == application_id
