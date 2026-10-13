"""Customer-facing endpoints (applications, payments) only open to the record's owner:
the logged-in customer, or the browser holding the signed guest token issued when the
application was created. Anyone else - even knowing the id - gets a plain 404."""

from sqlalchemy import select


async def _guest_application(client, db_session, phone="0700123123"):
    from app.models.customer import Customer

    res = await client.post("/api/v1/quotes", json={"category": "motor", "answers": {"owner_phone": phone, "owner_name": "Owner Test"}})
    quote = res.json()["quotes"][0]
    customer = await db_session.scalar(select(Customer).where(Customer.phone == phone))
    app_res = await client.post("/api/v1/applications", json={"quote_id": quote["id"], "customer_id": str(customer.id), "applicant_details": {}})
    assert app_res.status_code == 200, app_res.text
    return app_res, quote, customer


async def test_creating_an_application_hands_back_a_guest_token(client, db_session, seeded_providers):
    app_res, _, _ = await _guest_application(client, db_session)
    assert app_res.headers.get("X-Guest-Token")


async def test_the_owner_can_read_their_application_but_a_stranger_cannot(client, stranger_client, db_session, seeded_providers):
    app_res, _, _ = await _guest_application(client, db_session)
    application_id = app_res.json()["id"]

    assert (await client.get(f"/api/v1/applications/{application_id}/status")).status_code == 200
    # knowing the id is not enough
    for path in ("status", "documents/checklist", "discount"):
        assert (await stranger_client.get(f"/api/v1/applications/{application_id}/{path}")).status_code == 404
    assert (await stranger_client.post(f"/api/v1/applications/{application_id}/submit")).status_code == 404


async def test_a_stranger_cannot_start_or_read_a_payment(client, stranger_client, db_session, seeded_providers):
    from app.services.application_service import approve_application

    app_res, quote, customer = await _guest_application(client, db_session, phone="0700123456")
    application_id = app_res.json()["id"]
    await client.post(f"/api/v1/applications/{application_id}/submit")
    await approve_application(db_session, application_id)

    body = {"application_id": application_id, "customer_id": str(customer.id), "amount": quote["total"], "phone": "0700123456", "method": "mpesa"}
    assert (await stranger_client.post("/api/v1/payments/initiate", json=body)).status_code == 404

    paid = await client.post("/api/v1/payments/initiate", json=body)
    assert paid.status_code == 200, paid.text
    payment_id = paid.json()["payment_id"]
    assert (await client.get(f"/api/v1/payments/{payment_id}/status")).status_code == 200
    assert (await stranger_client.get(f"/api/v1/payments/{payment_id}/status")).status_code == 404


async def test_a_guest_token_for_one_application_does_not_open_another(client, stranger_client, db_session, seeded_providers):
    first, _, _ = await _guest_application(client, db_session, phone="0700222001")
    second, _, _ = await _guest_application(client, db_session, phone="0700222002")
    first_token = first.headers["X-Guest-Token"]
    first_id, second_id = first.json()["id"], second.json()["id"]

    # presenting only the first application's token opens the first application...
    assert (await stranger_client.get(f"/api/v1/applications/{first_id}/status", headers={"X-Guest-Token": first_token})).status_code == 200
    # ...and nothing else, not even another application created in the same browser session
    assert (await stranger_client.get(f"/api/v1/applications/{second_id}/status", headers={"X-Guest-Token": first_token})).status_code == 404


async def test_you_cannot_open_an_application_under_someone_elses_customer_id(client, db_session, seeded_providers):
    from app.models.customer import Customer

    res = await client.post("/api/v1/quotes", json={"category": "motor", "answers": {"owner_phone": "0700333001", "owner_name": "Real Owner"}})
    quote = res.json()["quotes"][0]
    victim = Customer(full_name="Victim", phone="0700333999")
    db_session.add(victim)
    await db_session.commit()

    spoof = await client.post("/api/v1/applications", json={"quote_id": quote["id"], "customer_id": str(victim.id), "applicant_details": {}})
    assert spoof.status_code == 403
