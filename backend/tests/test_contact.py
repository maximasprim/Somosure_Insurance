from sqlalchemy import select


async def test_contact_form_creates_customer_and_lead(client, db_session):
    from app.models.crm import Communication, Lead
    from app.models.customer import Customer

    res = await client.post(
        "/api/v1/contact",
        json={"full_name": "Contact Test", "phone": "0788222333", "email": "contact@example.com", "message": "I have a question about business cover."},
    )
    assert res.status_code == 200
    assert res.json()["received"] is True

    customer = await db_session.scalar(select(Customer).where(Customer.phone == "0788222333"))
    assert customer is not None
    assert customer.full_name == "Contact Test"

    lead = await db_session.scalar(select(Lead).where(Lead.customer_id == customer.id))
    assert lead is not None
    assert lead.stage == "new"

    communications = (await db_session.scalars(select(Communication).where(Communication.customer_id == customer.id))).all()
    assert len(communications) == 1
    assert "business cover" in communications[0].body


async def test_repeat_contact_reuses_customer_and_lead(client, db_session):
    from app.models.crm import Lead
    from app.models.customer import Customer

    payload = {"full_name": "Repeat Contact", "phone": "0788333444", "message": "First message"}
    await client.post("/api/v1/contact", json=payload)
    await client.post("/api/v1/contact", json={**payload, "message": "Second message"})

    customers = (await db_session.scalars(select(Customer).where(Customer.phone == "0788333444"))).all()
    assert len(customers) == 1

    leads = (await db_session.scalars(select(Lead).where(Lead.customer_id == customers[0].id))).all()
    assert len(leads) == 1, "a second contact message should advance the existing lead, not duplicate it"


async def test_contact_form_requires_no_authentication(client):
    """The whole point of a public contact form - no token, no login."""
    res = await client.post("/api/v1/contact", json={"full_name": "Anon", "phone": "0788555666", "message": "Hi"})
    assert res.status_code == 200
