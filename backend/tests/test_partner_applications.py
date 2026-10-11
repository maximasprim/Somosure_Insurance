"""Partner applications: the public form, the team alert, and the staff
approve/decline queue (approving creates the partner, and can enrol them as an
affiliate). Needs the same real Postgres as the rest of the suite."""

import uuid
from decimal import Decimal

from sqlalchemy import func, select

PUBLIC = "/api/v1/partner-applications"
ADMIN = "/api/v1/admin/partner-applications"


def _form(**overrides):
    body = {
        "business_name": "Kamau Motors Ltd",
        "partner_type": "car_dealer",
        "contact_name": "Peter Kamau",
        "contact_email": "Peter@KamauMotors.example",
        "contact_phone": "0712345678",
        "town": "Nairobi",
        "website": "https://kamaumotors.example",
        "working_model": "both",
        "monthly_clients": "11-50",
        "products": ["motor", "medical"],
        "message": "We sell about forty used cars a month and want to insure every buyer through you.",
        "consent": True,
    }
    body.update(overrides)
    return body


async def _staff_token(client, db_session, email, role, name="Partner Tester"):
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


async def _count(db_session, model=None):
    from app.models.partner import PartnerApplication

    return await db_session.scalar(select(func.count()).select_from(model or PartnerApplication))


async def _submit(client, **overrides):
    return await client.post(PUBLIC, json=_form(**overrides))


# ---------------------------------------------------------------- public form


async def test_anyone_can_apply_without_logging_in(client, db_session):
    from app.models.partner import PartnerApplication

    res = await _submit(client)
    assert res.status_code == 201
    body = res.json()
    assert body["received"] is True and body["reference"].startswith("SOM-PTR-")

    row = await db_session.scalar(select(PartnerApplication).where(PartnerApplication.reference == body["reference"]))
    assert row.status == "pending" and row.business_name == "Kamau Motors Ltd" and row.partner_type == "car_dealer"
    assert row.contact_email == "peter@kamaumotors.example"  # tidied to lower case
    assert row.working_model == "both" and row.monthly_clients == "11-50" and row.products == ["motor", "medical"]


async def test_a_bad_application_is_refused_with_a_clear_reason(client):
    cases = {
        "bad email": {"contact_email": "not-an-email"},
        "short phone": {"contact_phone": "07123"},
        "message too short": {"message": "hi"},
        "unknown type": {"partner_type": "pirate"},
        "unknown product": {"products": ["motor", "unicorns"]},
        "no consent": {"consent": False},
        "bad volume": {"monthly_clients": "a million"},
        "missing name": {"business_name": ""},
    }
    for label, change in cases.items():
        res = await client.post(PUBLIC, json=_form(**change))
        assert res.status_code == 422, label


async def test_a_bot_that_fills_the_hidden_field_looks_successful_but_stores_nothing(client, db_session):
    res = await _submit(client, fax="call me maybe")
    assert res.status_code == 201
    assert await _count(db_session) == 0


async def test_applying_twice_does_not_create_a_second_application_or_a_second_alert(client, db_session, monkeypatch):
    from app.api.v1 import partner_applications

    alerts = []

    async def record(application):
        alerts.append(application["reference"])

    monkeypatch.setattr(partner_applications, "alert_team", record)

    first = (await _submit(client)).json()
    same_email = (await _submit(client, contact_email="PETER@kamaumotors.example", contact_phone="0799000111")).json()
    same_phone = (await _submit(client, contact_email="other@example.com", contact_phone="+254 712 345 678")).json()

    assert first["reference"] == same_email["reference"] == same_phone["reference"]
    assert await _count(db_session) == 1
    assert alerts == [first["reference"]]  # the team was only told once


async def test_after_a_decision_the_same_person_can_apply_again(client, db_session):
    token, _ = await _staff_token(client, db_session, "again@example.com", "management")
    auth = {"Authorization": f"Bearer {token}"}
    first = (await _submit(client)).json()
    row = (await client.get(ADMIN, headers=auth)).json()["items"][0]
    await client.post(f"{ADMIN}/{row['id']}/decline", json={"reason": "Not a fit right now"}, headers=auth)
    second = (await _submit(client)).json()
    assert second["reference"] != first["reference"] and await _count(db_session) == 2


# ----------------------------------------------------------------- team alert


async def test_the_alert_text_has_what_staff_need_to_act(db_session):
    from app.models.partner import PartnerApplication
    from app.services.partner_application_service import alert_text, snapshot

    application = PartnerApplication(
        reference="SOM-PTR-2026-123456", business_name="Kamau Motors Ltd", partner_type="car_dealer", contact_name="Peter Kamau",
        contact_email="peter@kamaumotors.example", contact_phone="0712345678", town="Nairobi", working_model="both",
        monthly_clients="11-50", products=["motor"], message="We sell forty cars a month.", status="pending",
    )
    subject, body, sms = alert_text(snapshot(application))
    assert "Kamau Motors Ltd" in subject and "Car dealer" in subject
    for needle in ("SOM-PTR-2026-123456", "Peter Kamau", "0712345678", "peter@kamaumotors.example", "11-50", "We sell forty cars a month.", "/admin/partner-applications"):
        assert needle in body, needle
    assert "SOM-PTR-2026-123456" in sms and len(sms) < 200


async def test_the_team_is_emailed_and_texted_and_one_failure_does_not_stop_the_rest(monkeypatch):
    from app.notifications import registry
    from app.notifications.base import DispatchResult
    from app.services import partner_application_service as svc

    class _Settings:
        partner_alert_emails = "boss@example.com, ops@example.com"
        partner_alert_phones = "0700111222"
        frontend_base_url = "https://somosure.example"

    emails, texts = [], []

    class _Email:
        async def send_email(self, to, subject, body):
            if to == "boss@example.com":
                raise RuntimeError("mail server down")
            emails.append((to, subject))
            return DispatchResult(delivered=True)

    class _Sms:
        async def send_sms(self, phone, body):
            texts.append(phone)
            return DispatchResult(delivered=True)

    monkeypatch.setattr(svc, "get_settings", lambda: _Settings())
    monkeypatch.setattr(registry, "get_email_dispatcher", lambda: _Email())
    monkeypatch.setattr(registry, "get_dispatcher", lambda: _Sms())

    data = {
        "reference": "SOM-PTR-2026-000001", "business_name": "Acme Sacco", "partner_type": "sacco", "contact_name": "Jane",
        "contact_email": "jane@acme.example", "contact_phone": "0700000000", "town": None, "working_model": "referrals",
        "monthly_clients": "1-10", "products": None, "message": "We'd like to offer cover to our members.",
    }
    await svc.alert_team(data)  # must not raise even though the first email fails
    assert [e[0] for e in emails] == ["ops@example.com"] and "Acme Sacco" in emails[0][1]
    assert texts == ["0700111222"]


async def test_with_no_alert_recipients_nothing_is_sent_and_nothing_breaks(monkeypatch):
    from app.notifications import registry
    from app.services import partner_application_service as svc

    class _Settings:
        partner_alert_emails = ""
        partner_alert_phones = ""
        frontend_base_url = "https://somosure.example"

    def boom():
        raise AssertionError("no dispatcher should be used")

    monkeypatch.setattr(svc, "get_settings", lambda: _Settings())
    monkeypatch.setattr(registry, "get_email_dispatcher", boom)
    monkeypatch.setattr(registry, "get_dispatcher", boom)
    await svc.alert_team({
        "reference": "SOM-PTR-2026-000002", "business_name": "Quiet Ltd", "partner_type": "sme", "contact_name": "Q",
        "contact_email": "q@example.com", "contact_phone": "0700000001", "town": None, "working_model": "both",
        "monthly_clients": "1-10", "products": None, "message": "Interested in partnering with you.",
    })


async def test_a_tuple_in_the_frontend_url_setting_still_gives_a_usable_link(monkeypatch):
    from app.services import partner_application_service as svc

    class _Settings:
        frontend_base_url = ("http://localhost:3000", "https://somosure.example")

    monkeypatch.setattr(svc, "get_settings", lambda: _Settings())
    assert svc._frontend_base() == "http://localhost:3000"


# ------------------------------------------------------------- staff queue


async def test_only_management_can_see_the_queue(client, db_session):
    await _submit(client)
    for email, role in (("c@example.com", "customer"), ("o@example.com", "operations")):
        token, _ = await _staff_token(client, db_session, email, role)
        assert (await client.get(ADMIN, headers={"Authorization": f"Bearer {token}"})).status_code == 403
    assert (await client.get(ADMIN)).status_code == 401
    token, _ = await _staff_token(client, db_session, "m@example.com", "management")
    assert (await client.get(ADMIN, headers={"Authorization": f"Bearer {token}"})).status_code == 200


async def test_the_queue_lists_waiting_applications_first_and_counts_them(client, db_session):
    token, _ = await _staff_token(client, db_session, "queue@example.com", "management")
    auth = {"Authorization": f"Bearer {token}"}
    await _submit(client, business_name="First Dealer", contact_email="a@a.example", contact_phone="0700000011")
    await _submit(client, business_name="Second Sacco", partner_type="sacco", contact_email="b@b.example", contact_phone="0700000022")
    page = (await client.get(ADMIN, headers=auth)).json()
    assert page["total"] == 2 and page["pending_count"] == 2
    assert [i["business_name"] for i in page["items"]] == ["First Dealer", "Second Sacco"]  # longest-waiting first

    first = page["items"][0]["id"]
    await client.post(f"{ADMIN}/{first}/decline", json={"reason": "Outside our service area"}, headers=auth)
    after = (await client.get(ADMIN, headers=auth)).json()
    assert after["pending_count"] == 1 and after["items"][0]["business_name"] == "Second Sacco"  # waiting ones stay on top
    declined = (await client.get(ADMIN, params={"status": "declined"}, headers=auth)).json()
    assert [i["business_name"] for i in declined["items"]] == ["First Dealer"]
    found = (await client.get(ADMIN, params={"q": "sacco"}, headers=auth)).json()
    assert [i["business_name"] for i in found["items"]] == ["Second Sacco"]


# ---------------------------------------------------------------- approving


async def test_approving_creates_the_partner_and_records_who_and_why(client, db_session):
    from app.models.partner import Partner

    token, manager = await _staff_token(client, db_session, "approve@example.com", "management", "Mary Manager")
    auth = {"Authorization": f"Bearer {token}"}
    await _submit(client)
    application = (await client.get(ADMIN, headers=auth)).json()["items"][0]

    # a reason is required
    assert (await client.post(f"{ADMIN}/{application['id']}/approve", json={"reason": ""}, headers=auth)).status_code == 422

    res = await client.post(f"{ADMIN}/{application['id']}/approve", json={"reason": "Established dealer with good volumes"}, headers=auth)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["application"]["status"] == "approved" and body["application"]["decision_reason"] == "Established dealer with good volumes"
    assert body["affiliate_code"] is None and body["warnings"] == []

    partner = await db_session.get(Partner, uuid.UUID(body["partner_id"]))
    assert partner.name == "Kamau Motors Ltd" and partner.partner_type == "car_dealer" and partner.is_active
    assert partner.contact_name == "Peter Kamau" and partner.contact_email == "peter@kamaumotors.example"
    assert partner.managed_by_user_id == manager.id

    # it shows up in the existing Partners screen's list too
    listed = (await client.get("/api/v1/admin/partners", headers=auth)).json()
    assert any(p["name"] == "Kamau Motors Ltd" for p in listed)

    # a decision can't be made twice
    assert (await client.post(f"{ADMIN}/{application['id']}/approve", json={"reason": "Again"}, headers=auth)).status_code == 409
    assert (await client.post(f"{ADMIN}/{application['id']}/decline", json={"reason": "Changed my mind"}, headers=auth)).status_code == 409
    assert await _count(db_session, Partner) == 1


async def test_the_approver_can_correct_the_partner_type(client, db_session):
    from app.models.partner import Partner

    token, _ = await _staff_token(client, db_session, "type@example.com", "management")
    auth = {"Authorization": f"Bearer {token}"}
    await _submit(client, partner_type="sme")
    application = (await client.get(ADMIN, headers=auth)).json()["items"][0]
    body = (await client.post(f"{ADMIN}/{application['id']}/approve", json={"reason": "Actually a bank agent", "partner_type": "agent"}, headers=auth)).json()
    assert (await db_session.get(Partner, uuid.UUID(body["partner_id"]))).partner_type == "agent"


async def test_approving_can_enrol_them_as_an_affiliate_with_a_rate_and_a_discount(client, db_session):
    from app.models.affiliate import Affiliate, AffiliateRateRule, ReferralDiscount
    from app.models.customer import Customer
    from app.services.affiliate_service import get_affiliate_settings

    settings = await get_affiliate_settings(db_session)
    settings.program_enabled = True
    await db_session.commit()

    token, _ = await _staff_token(client, db_session, "enrol@example.com", "management")
    auth = {"Authorization": f"Bearer {token}"}
    await _submit(client)
    application = (await client.get(ADMIN, headers=auth)).json()["items"][0]

    res = await client.post(
        f"{ADMIN}/{application['id']}/approve",
        json={
            "reason": "Strong dealer - give them a good rate", "enrol_affiliate": True,
            "commission_type": "percent", "commission_value": "10",
            "discount_type": "percent", "discount_value": "5", "discount_valid_days": 90,
        },
        headers=auth,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["affiliate_code"].startswith("AFF") and body["affiliate_link_path"] == f"/?ref={body['affiliate_code']}"
    assert body["commission_rule_created"] is True and body["discount_credit_created"] is True and body["warnings"] == []

    customer = await db_session.scalar(select(Customer).where(Customer.email == "peter@kamaumotors.example"))
    assert customer is not None and customer.full_name == "Peter Kamau"
    affiliate = await db_session.scalar(select(Affiliate).where(Affiliate.customer_id == customer.id))
    assert affiliate.code == body["affiliate_code"] and affiliate.status == "active" and affiliate.payout_phone == customer.phone

    rule = await db_session.scalar(select(AffiliateRateRule).where(AffiliateRateRule.affiliate_customer_id == customer.id))
    assert rule.rate_type == "percent" and rule.rate_value == Decimal("10.00") and rule.active and "Kamau Motors" in rule.name

    credit = await db_session.scalar(select(ReferralDiscount).where(ReferralDiscount.customer_id == customer.id))
    assert credit.status == "available" and credit.source == "manual" and credit.discount_value == Decimal("5.00") and "Kamau Motors" in credit.note


async def test_an_existing_customer_is_reused_not_duplicated(client, db_session):
    from app.models.customer import Customer

    token, _ = await _staff_token(client, db_session, "reuse@example.com", "management")
    auth = {"Authorization": f"Bearer {token}"}
    existing = Customer(full_name="Peter K.", phone="+254712345678", email=None)
    db_session.add(existing)
    await db_session.commit()

    await _submit(client, contact_phone="0712345678")  # same number, written differently
    application = (await client.get(ADMIN, headers=auth)).json()["items"][0]
    await client.post(f"{ADMIN}/{application['id']}/approve", json={"reason": "Welcome", "enrol_affiliate": True}, headers=auth)
    customers = (await db_session.scalars(select(Customer).where(Customer.phone.in_(["+254712345678", "0712345678"])))).all()
    assert len(customers) == 1 and customers[0].id == existing.id


async def test_you_are_warned_when_the_affiliate_program_is_still_off(client, db_session):
    token, _ = await _staff_token(client, db_session, "warn@example.com", "management")
    auth = {"Authorization": f"Bearer {token}"}
    await _submit(client)
    application = (await client.get(ADMIN, headers=auth)).json()["items"][0]
    body = (await client.post(f"{ADMIN}/{application['id']}/approve", json={"reason": "Welcome", "enrol_affiliate": True}, headers=auth)).json()
    assert body["affiliate_code"] is not None
    assert len(body["warnings"]) == 1 and "switched off" in body["warnings"][0]


async def test_the_affiliate_options_are_checked_before_anything_is_created(client, db_session):
    from app.models.partner import Partner

    token, _ = await _staff_token(client, db_session, "bad@example.com", "management")
    auth = {"Authorization": f"Bearer {token}"}
    await _submit(client)
    application = (await client.get(ADMIN, headers=auth)).json()["items"][0]
    url = f"{ADMIN}/{application['id']}/approve"
    bad_bodies = [
        {"reason": "ok", "commission_type": "percent", "commission_value": "10"},  # rate without enrolling
        {"reason": "ok", "enrol_affiliate": True, "commission_value": "10"},  # value without a type
        {"reason": "ok", "enrol_affiliate": True, "discount_type": "percent"},  # type without a value
        {"reason": "ok", "enrol_affiliate": True, "commission_type": "percent", "commission_value": "150"},
        {"reason": "ok", "enrol_affiliate": True, "discount_type": "percent", "discount_value": "150"},
    ]
    for body in bad_bodies:
        assert (await client.post(url, json=body, headers=auth)).status_code == 422, body
    assert await _count(db_session, Partner) == 0  # nothing half-created
    assert (await client.get(f"{ADMIN}/{application['id']}", headers=auth)).json()["status"] == "pending"


# ----------------------------------------------------------------- declining


async def test_declining_keeps_the_reason_and_creates_nothing(client, db_session):
    from app.models.affiliate import Affiliate
    from app.models.partner import Partner

    token, _ = await _staff_token(client, db_session, "decline@example.com", "management")
    auth = {"Authorization": f"Bearer {token}"}
    await _submit(client)
    application = (await client.get(ADMIN, headers=auth)).json()["items"][0]
    assert (await client.post(f"{ADMIN}/{application['id']}/decline", json={"reason": ""}, headers=auth)).status_code == 422

    res = await client.post(f"{ADMIN}/{application['id']}/decline", json={"reason": "We don't cover that area yet"}, headers=auth)
    assert res.status_code == 200 and res.json()["status"] == "declined" and res.json()["decision_reason"] == "We don't cover that area yet"
    assert await _count(db_session, Partner) == 0 and await _count(db_session, Affiliate) == 0
    assert (await client.get(f"{ADMIN}/{uuid.uuid4()}", headers=auth)).status_code == 404


async def test_decisions_are_on_the_audit_trail_with_who_and_why(client, db_session):
    from app.models.audit import AuditLog

    token, _ = await _staff_token(client, db_session, "audit-p@example.com", "management", "Audrey Approver")
    auth = {"Authorization": f"Bearer {token}"}
    await _submit(client)
    application = (await client.get(ADMIN, headers=auth)).json()["items"][0]
    await client.post(f"{ADMIN}/{application['id']}/approve", json={"reason": "Great fit for our dealer network"}, headers=auth)
    row = await db_session.scalar(
        select(AuditLog).where(AuditLog.kind == "change", AuditLog.entity_type == "partner_applications", AuditLog.action == "updated")
    )
    assert row.actor_name == "Audrey Approver" and row.reason == "Great fit for our dealer network" and row.changes["status"][1] == "approved"
