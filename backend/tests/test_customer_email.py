"""The customer's email, captured on the quote form and kept on the customer record."""

from sqlalchemy import func, select

from app.models.customer import Customer
from app.models.quote import QuoteRequest


async def _customer(db_session, phone):
    return await db_session.scalar(select(Customer).where(Customer.phone == phone))


async def test_an_email_typed_on_the_quote_form_is_saved_on_the_customer(client, db_session, seeded_providers):
    res = await client.post(
        "/api/v1/quotes",
        json={"category": "motor", "answers": {"owner_name": "Email Tester", "owner_phone": "0733100001", "owner_email": "  Jane.Doe@Example.COM "}},
    )
    assert res.status_code == 200, res.text
    assert (await _customer(db_session, "0733100001")).email == "jane.doe@example.com"  # tidied and lower-cased


async def test_the_other_forms_call_it_email_and_it_is_saved_too(client, db_session, seeded_providers):
    res = await client.post(
        "/api/v1/quotes",
        json={"category": "medical", "answers": {"full_name": "Generic Tester", "phone": "0733100002", "email": "generic@example.com", "primary_age": 30}},
    )
    assert res.status_code == 200, res.text
    assert (await _customer(db_session, "0733100002")).email == "generic@example.com"


async def test_the_email_is_optional(client, db_session, seeded_providers):
    res = await client.post("/api/v1/quotes", json={"category": "motor", "answers": {"owner_name": "No Email", "owner_phone": "0733100003", "owner_email": ""}})
    assert res.status_code == 200
    assert (await _customer(db_session, "0733100003")).email is None


async def test_a_later_quote_fills_a_missing_email_but_never_overwrites_one_we_hold(client, db_session, seeded_providers):
    phone = "0733100004"
    await client.post("/api/v1/quotes", json={"category": "motor", "answers": {"owner_name": "Gradual", "owner_phone": phone}})
    assert (await _customer(db_session, phone)).email is None

    await client.post("/api/v1/quotes", json={"category": "motor", "answers": {"owner_name": "Gradual", "owner_phone": phone, "owner_email": "first@example.com"}})
    await db_session.commit()  # end this test session's snapshot so it sees the API's committed change
    db_session.expire_all()
    assert (await _customer(db_session, phone)).email == "first@example.com"

    await client.post("/api/v1/quotes", json={"category": "motor", "answers": {"owner_name": "Gradual", "owner_phone": phone, "owner_email": "second@example.com"}})
    db_session.expire_all()
    assert (await _customer(db_session, phone)).email == "first@example.com"  # the one already on file is kept


async def test_something_that_is_not_an_email_is_refused_with_a_clear_message_and_nothing_is_created(client, db_session, seeded_providers):
    before = await db_session.scalar(select(func.count(QuoteRequest.id)))
    res = await client.post("/api/v1/quotes", json={"category": "motor", "answers": {"owner_name": "Typo", "owner_phone": "0733100005", "owner_email": "not-an-email"}})
    assert res.status_code == 422 and "valid email" in res.json()["detail"]
    assert await _customer(db_session, "0733100005") is None
    assert await db_session.scalar(select(func.count(QuoteRequest.id))) == before
