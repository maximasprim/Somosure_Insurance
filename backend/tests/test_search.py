async def _staff_headers(client, db_session, email="searchstaff@example.com"):
    import uuid

    from app.models.user import Role, User, UserRole
    from app.core.security import hash_password

    await client.post("/api/v1/auth/register", json={"full_name": "Search Staff", "email": email, "password": "supersecret1"})
    from sqlalchemy import select

    user = await db_session.scalar(select(User).where(User.email == email))
    role = Role(id=uuid.uuid4(), name="operations")
    db_session.add(role)
    await db_session.flush()
    await db_session.execute(UserRole.__table__.delete().where(UserRole.user_id == user.id))
    db_session.add(UserRole(user_id=user.id, role_id=role.id))
    await db_session.commit()

    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "supersecret1"})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def test_search_finds_customer_by_phone(client, db_session):
    from app.models.customer import Customer

    db_session.add(Customer(full_name="Searchable Person", phone="0799111222"))
    await db_session.commit()

    headers = await _staff_headers(client, db_session)
    res = await client.get("/api/v1/admin/search", params={"q": "0799111222"}, headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert len(body["customers"]) == 1
    assert body["customers"][0]["full_name"] == "Searchable Person"


async def test_search_finds_policy_by_number(client, db_session, seeded_providers):
    from datetime import date
    from decimal import Decimal

    from app.models.application import Application
    from app.models.customer import Customer
    from app.models.policy import Policy
    from app.models.quote import Quote, QuoteRequest

    customer = Customer(full_name="Policy Search Test", phone="0799333444")
    db_session.add(customer)
    await db_session.flush()
    qr = QuoteRequest(reference="SOM-2026-333444", customer_id=customer.id, category="motor", status="quoted")
    db_session.add(qr)
    await db_session.flush()
    quote = Quote(quote_request_id=qr.id, provider_id=seeded_providers[0].id, premium=Decimal("1000"), taxes=Decimal("0"), fees=Decimal("0"), total=Decimal("1000"), is_mock=True, status="selected")
    db_session.add(quote)
    await db_session.flush()
    application = Application(reference="SOM-APP-2026-333444", quote_id=quote.id, customer_id=customer.id, status="approved")
    db_session.add(application)
    await db_session.flush()
    policy = Policy(
        policy_number="SEARCHABLE-POL-999", application_id=application.id, provider_id=seeded_providers[0].id,
        customer_id=customer.id, start_date=date.today(), end_date=date(date.today().year + 1, 1, 1),
        premium=Decimal("1000"), status="active", is_mock=True,
    )
    db_session.add(policy)
    await db_session.commit()

    headers = await _staff_headers(client, db_session, email="searchstaff2@example.com")
    res = await client.get("/api/v1/admin/search", params={"q": "SEARCHABLE-POL"}, headers=headers)
    assert res.status_code == 200
    assert len(res.json()["policies"]) == 1


async def test_search_requires_staff_role(client):
    await client.post("/api/v1/auth/register", json={"full_name": "Plain", "email": "searchplain@example.com", "password": "supersecret1"})
    login = await client.post("/api/v1/auth/login", json={"email": "searchplain@example.com", "password": "supersecret1"})
    token = login.json()["access_token"]

    res = await client.get("/api/v1/admin/search", params={"q": "test"}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403
