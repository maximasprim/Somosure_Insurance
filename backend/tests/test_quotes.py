from decimal import Decimal


async def test_motor_quote_returns_quotes_from_all_active_providers(client, db_session, seeded_providers):
    """Seeded demo providers are 3 single-insurer + 1 aggregator (3
    underlying insurers) = 6 quote rows expected from one request."""
    res = await client.post("/api/v1/quotes", json={"category": "motor", "answers": {"owner_phone": "0700111222", "owner_name": "Test Guest"}})
    assert res.status_code == 200
    body = res.json()
    assert body["category"] == "motor"
    assert body["status"] == "quoted"
    # 3 single-insurer demo providers + 3 from the demo aggregator = 6
    assert len(body["quotes"]) == 6


async def test_guest_quote_creates_a_customer_and_a_lead(client, db_session, seeded_providers):
    from sqlalchemy import select

    from app.models.crm import Lead
    from app.models.customer import Customer

    res = await client.post(
        "/api/v1/quotes",
        json={"category": "motor", "answers": {"owner_phone": "0711222333", "owner_name": "Guest Lead Test"}},
    )
    assert res.status_code == 200

    customer = await db_session.scalar(select(Customer).where(Customer.phone == "0711222333"))
    assert customer is not None
    assert customer.full_name == "Guest Lead Test"

    lead = await db_session.scalar(select(Lead).where(Lead.customer_id == customer.id))
    assert lead is not None
    assert lead.stage == "quote"
    assert lead.product_interest == "motor"


async def test_repeat_guest_quote_reuses_customer_and_advances_same_lead(client, db_session, seeded_providers):
    from sqlalchemy import select

    from app.models.crm import Lead
    from app.models.customer import Customer

    answers = {"owner_phone": "0722333444", "owner_name": "Repeat Guest"}
    await client.post("/api/v1/quotes", json={"category": "motor", "answers": answers})
    await client.post("/api/v1/quotes", json={"category": "medical", "answers": answers})

    customers = (await db_session.scalars(select(Customer).where(Customer.phone == "0722333444"))).all()
    assert len(customers) == 1, "the same phone number should resolve to one customer, not two"

    leads = (await db_session.scalars(select(Lead).where(Lead.customer_id == customers[0].id))).all()
    assert len(leads) == 1, "a second quote request should advance the existing lead, not create a duplicate"
    assert leads[0].product_interest == "medical"  # updated to the latest request


async def test_aggregator_quotes_are_tagged_with_distinct_underlying_insurers(client, seeded_providers):
    res = await client.post("/api/v1/quotes", json={"category": "motor", "answers": {"owner_phone": "0733444555", "owner_name": "Agg Test"}})
    quotes = res.json()["quotes"]

    aggregator_quotes = [q for q in quotes if q["underlying_provider_name"] is not None]
    assert len(aggregator_quotes) == 3, "the demo aggregator should contribute exactly 3 underlying-insurer quotes"

    underlying_names = {q["underlying_provider_name"] for q in aggregator_quotes}
    assert len(underlying_names) == 3, "each aggregator quote should name a distinct underlying insurer"

    totals = {q["total"] for q in aggregator_quotes}
    assert len(totals) == 3, "each underlying insurer's quote should be distinctly priced"

    for q in aggregator_quotes:
        assert "via" in q["provider_name"], "aggregator-sourced quotes should show 'X (via Aggregator)' in the display name"


async def test_direct_insurer_quotes_have_no_underlying_provider_name(client, seeded_providers):
    res = await client.post("/api/v1/quotes", json={"category": "motor", "answers": {"owner_phone": "0744555666", "owner_name": "Direct Test"}})
    quotes = res.json()["quotes"]
    direct_quotes = [q for q in quotes if q["underlying_provider_name"] is None]
    assert len(direct_quotes) == 3, "the 3 seeded single-insurer demo providers should each return exactly one direct quote"


async def test_non_motor_category_also_resolves_guest_customer(client, db_session, seeded_providers):
    """Regression test for the frontend bug just fixed: any category's
    quote form (not just motor) must resolve to a real Customer via the
    phone/full_name fields, since an application can't be created against
    a customer_id that doesn't exist in the database."""
    from sqlalchemy import select

    from app.models.customer import Customer

    res = await client.post(
        "/api/v1/quotes",
        json={"category": "medical", "answers": {"phone": "0766111222", "full_name": "Medical Guest"}},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["customer_id"] is not None

    customer = await db_session.scalar(select(Customer).where(Customer.phone == "0766111222"))
    assert customer is not None
    assert str(customer.id) == body["customer_id"]

    # Confirm an application can actually be created against this resolved
    # customer_id - proving the frontend's read of body["customer_id"]
    # would produce a working request, not a foreign-key violation.
    quote = body["quotes"][0]
    app_res = await client.post(
        "/api/v1/applications",
        json={"quote_id": quote["id"], "customer_id": body["customer_id"], "applicant_details": {}},
    )
    assert app_res.status_code == 200


async def test_quote_reference_format(client, seeded_providers):
    res = await client.post("/api/v1/quotes", json={"category": "motor", "answers": {"owner_phone": "0755666777", "owner_name": "Ref Test"}})
    body = res.json()
    assert body["reference"].startswith("SOM-")
    parts = body["reference"].split("-")
    assert len(parts) == 3
    assert len(parts[1]) == 4  # year
    assert len(parts[2]) == 6  # sequence
    res = await client.post("/api/v1/quotes", json={"category": "motor", "answers": {"owner_phone": "0755666777", "owner_name": "Ref Test"}})
    body = res.json()
    assert body["reference"].startswith("SOM-")
    parts = body["reference"].split("-")
    assert len(parts) == 3
    assert len(parts[1]) == 4  # year
    assert len(parts[2]) == 6  # sequence
