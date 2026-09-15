from decimal import Decimal

from sqlalchemy import select


async def test_eligibility_matches_spec_worked_example(client, db_session, seeded_providers):
    """Spec §14's own worked example: KES 30,000 premium -> 20% deposit
    (6,000) -> 80% financed (24,000)."""
    from app.models.customer import Customer
    from app.models.provider import InsuranceProvider
    from app.models.quote import Quote, QuoteRequest

    customer = Customer(full_name="Financing Test", phone="0788999000")
    db_session.add(customer)
    await db_session.flush()

    provider = seeded_providers[0]
    qr = QuoteRequest(reference="SOM-2026-999999", customer_id=customer.id, category="motor", status="quoted")
    db_session.add(qr)
    await db_session.flush()

    quote = Quote(
        quote_request_id=qr.id, provider_id=provider.id, premium=Decimal("25862.00"), taxes=Decimal("4137.92"),
        fees=Decimal("0.08"), total=Decimal("30000.00"), currency="KES", is_mock=True, status="available",
    )
    db_session.add(quote)
    await db_session.commit()

    res = await client.post(
        "/api/v1/financing/eligibility",
        json={"customer_id": str(customer.id), "quote_id": str(quote.id), "term_months": 6},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["eligible"] is True
    assert Decimal(body["deposit_amount"]) == Decimal("6000.00")
    assert Decimal(body["financed_amount"]) == Decimal("24000.00")
    assert Decimal(body["monthly_installment"]) == Decimal("4000.00")


async def test_financing_application_creates_agreement_and_installment_schedule(client, db_session, seeded_providers):
    from app.models.customer import Customer
    from app.models.quote import Quote, QuoteRequest

    customer = Customer(full_name="Schedule Test", phone="0788999001")
    db_session.add(customer)
    await db_session.flush()

    qr = QuoteRequest(reference="SOM-2026-888888", customer_id=customer.id, category="motor", status="quoted")
    db_session.add(qr)
    await db_session.flush()

    quote = Quote(
        quote_request_id=qr.id, provider_id=seeded_providers[0].id, premium=Decimal("17241.38"), taxes=Decimal("2758.62"),
        fees=Decimal("0.00"), total=Decimal("20000.00"), currency="KES", is_mock=True, status="available",
    )
    db_session.add(quote)
    await db_session.commit()

    res = await client.post(
        "/api/v1/financing/applications",
        json={"customer_id": str(customer.id), "quote_id": str(quote.id), "term_months": 4},
    )
    assert res.status_code == 200
    application = res.json()
    assert application["status"] == "approved"

    agreement_res = await client.get(f"/api/v1/financing/applications/{application['id']}/agreement")
    assert agreement_res.status_code == 200
    agreement = agreement_res.json()
    assert agreement["term_months"] == 4
    assert len(agreement["installments"]) == 4

    # The schedule should sum exactly to the financed amount (spec §14) -
    # the last installment absorbs any rounding remainder.
    total_scheduled = sum(Decimal(i["amount"]) for i in agreement["installments"])
    assert total_scheduled == Decimal(application["financed_amount"])

    for i, installment in enumerate(agreement["installments"], start=1):
        assert installment["installment_number"] == i
        assert installment["status"] == "pending"


async def test_financing_rejects_amount_above_mock_ceiling(client, db_session, seeded_providers):
    from app.models.customer import Customer
    from app.models.quote import Quote, QuoteRequest

    customer = Customer(full_name="Too Big Test", phone="0788999002")
    db_session.add(customer)
    await db_session.flush()

    qr = QuoteRequest(reference="SOM-2026-777777", customer_id=customer.id, category="business", status="quoted")
    db_session.add(qr)
    await db_session.flush()

    # A premium so large that even after a 20% deposit, the financed
    # amount exceeds MOCK_MAX_FINANCED_AMOUNT (KES 200,000).
    quote = Quote(
        quote_request_id=qr.id, provider_id=seeded_providers[0].id, premium=Decimal("250000.00"), taxes=Decimal("40000.00"),
        fees=Decimal("0.00"), total=Decimal("500000.00"), currency="KES", is_mock=True, status="available",
    )
    db_session.add(quote)
    await db_session.commit()

    res = await client.post(
        "/api/v1/financing/eligibility",
        json={"customer_id": str(customer.id), "quote_id": str(quote.id), "term_months": 6},
    )
    body = res.json()
    assert body["eligible"] is False
    assert body["monthly_installment"] is None


async def test_financing_term_out_of_range_rejected(client, db_session, seeded_providers):
    from app.models.customer import Customer
    from app.models.quote import Quote, QuoteRequest

    customer = Customer(full_name="Bad Term Test", phone="0788999003")
    db_session.add(customer)
    await db_session.flush()
    qr = QuoteRequest(reference="SOM-2026-666666", customer_id=customer.id, category="motor", status="quoted")
    db_session.add(qr)
    await db_session.flush()
    quote = Quote(
        quote_request_id=qr.id, provider_id=seeded_providers[0].id, premium=Decimal("10000"), taxes=Decimal("0"),
        fees=Decimal("0"), total=Decimal("10000"), currency="KES", is_mock=True, status="available",
    )
    db_session.add(quote)
    await db_session.commit()

    res = await client.post(
        "/api/v1/financing/eligibility",
        json={"customer_id": str(customer.id), "quote_id": str(quote.id), "term_months": 15},
    )
    assert res.status_code == 400
