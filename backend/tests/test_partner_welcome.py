"""Approving a partner (a) creates a login for them and emails + texts a referral
link and a set-password link, and (b) registering with that same email attaches to
the partner's existing customer record instead of creating a duplicate."""

from sqlalchemy import func, select

from tests.test_partner_applications import ADMIN, _staff_token, _submit


class _Capture:
    """Stands in for both dispatchers and remembers what was sent."""

    is_mock = True

    def __init__(self):
        self.emails, self.sms = [], []

    async def send_email(self, email, subject, body):
        from app.notifications.base import DispatchResult

        self.emails.append((email, subject, body))
        return DispatchResult(delivered=True, is_mock=True)

    async def send_sms(self, phone, body):
        from app.notifications.base import DispatchResult

        self.sms.append((phone, body))
        return DispatchResult(delivered=True, is_mock=True)


async def _approve(client, db_session, monkeypatch, *, enrol=True, email="staff-welcome@example.com"):
    from app.notifications import registry

    cap = _Capture()
    monkeypatch.setattr(registry, "get_dispatcher", lambda: cap)
    monkeypatch.setattr(registry, "get_email_dispatcher", lambda: cap)
    token, _ = await _staff_token(client, db_session, email, "management")
    auth = {"Authorization": f"Bearer {token}"}
    await _submit(client)
    application = (await client.get(ADMIN, headers=auth)).json()["items"][0]
    res = await client.post(f"{ADMIN}/{application['id']}/approve", json={"reason": "Welcome", "enrol_affiliate": enrol}, headers=auth)
    assert res.status_code == 200, res.text
    return res.json(), cap


async def test_approval_creates_a_login_and_sends_both_links(client, db_session, monkeypatch):
    from app.models.customer import Customer
    from app.models.user import User

    body, cap = await _approve(client, db_session, monkeypatch)
    code = body["affiliate_code"]

    assert len(cap.emails) == 1 and len(cap.sms) == 1
    email_to, subject, text = cap.emails[0]
    assert email_to == "peter@kamaumotors.example" and "approved" in subject
    assert f"/?ref={code}" in text and "/reset-password?token=" in text
    assert f"/?ref={code}" in cap.sms[0][1] and "/reset-password?token=" in cap.sms[0][1]

    user = await db_session.scalar(select(User).where(User.email == "peter@kamaumotors.example"))
    customer = await db_session.scalar(select(Customer).where(Customer.email == "peter@kamaumotors.example"))
    assert user is not None and customer.user_id == user.id


async def test_the_emailed_link_lets_them_set_a_password_and_log_in(client, db_session, monkeypatch):
    _, cap = await _approve(client, db_session, monkeypatch)
    text = cap.emails[0][2]
    token = text.split("/reset-password?token=")[1].split()[0]

    res = await client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "my-new-password1"})
    assert res.status_code == 204
    login = await client.post("/api/v1/auth/login", json={"email": "peter@kamaumotors.example", "password": "my-new-password1"})
    assert login.status_code == 200
    # single use
    again = await client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "another-pass-123"})
    assert again.status_code == 400


async def test_without_enrolling_no_account_or_links_are_made(client, db_session, monkeypatch):
    from app.models.user import User

    body, cap = await _approve(client, db_session, monkeypatch, enrol=False)
    assert body["affiliate_code"] is None
    assert "reset-password" not in cap.emails[0][2] and "?ref=" not in cap.emails[0][2]
    assert await db_session.scalar(select(User).where(User.email == "peter@kamaumotors.example")) is None


async def test_an_existing_account_on_that_email_is_not_hijacked(client, db_session, monkeypatch):
    from app.models.customer import Customer

    # Someone already registered with the applicant's email (a separate customer record).
    await client.post("/api/v1/auth/register", json={"full_name": "Peter Kamau", "email": "peter@kamaumotors.example", "password": "supersecret1"})
    body, cap = await _approve(client, db_session, monkeypatch)
    assert any("already exists" in w for w in body["warnings"])
    assert "reset-password" not in cap.emails[0][2]
    assert await db_session.scalar(select(func.count()).select_from(Customer).where(Customer.email == "peter@kamaumotors.example")) >= 1


async def test_registering_later_attaches_to_the_partner_record_not_a_duplicate(client, db_session):
    """A partner customer record with no login (e.g. approved before this feature
    existed) is claimed when they register with the same email."""
    from app.models.affiliate import Affiliate
    from app.models.customer import Customer

    partner = Customer(full_name="Old Partner", phone="0700111222", email="oldpartner@example.com", lead_source="partner_application")
    db_session.add(partner)
    await db_session.flush()
    db_session.add(Affiliate(customer_id=partner.id, code="AFFTEST01", status="active"))
    await db_session.commit()

    res = await client.post("/api/v1/auth/register", json={"full_name": "Old Partner", "email": "OldPartner@example.com", "password": "supersecret1"})
    assert res.status_code == 201

    rows = (await db_session.scalars(select(Customer).where(func.lower(Customer.email) == "oldpartner@example.com"))).all()
    assert len(rows) == 1 and rows[0].id == partner.id and rows[0].user_id is not None


async def test_registering_does_not_claim_an_ordinary_guest_customer(client, db_session):
    """Email isn't verified at sign-up, so a guest customer (who may hold applications
    and documents) must NOT be handed to whoever registers their email."""
    from app.models.customer import Customer

    guest = Customer(full_name="Guest Person", phone="0700999888", email="guest@example.com", lead_source="website")
    db_session.add(guest)
    await db_session.commit()

    res = await client.post("/api/v1/auth/register", json={"full_name": "Someone Else", "email": "guest@example.com", "password": "supersecret1"})
    assert res.status_code == 201
    await db_session.refresh(guest)
    assert guest.user_id is None
