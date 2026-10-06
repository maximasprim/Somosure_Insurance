"""The smoother-quote-journey additions: category availability ("coming
soon"), document requirements, application status, document reuse for
financing, agent-callback leads and the extra eligibility context.

Needs the same real Postgres as the rest of the suite (see conftest.py).
DOCUMENT_VALIDATION is off for the suite, so uploads here are placeholder
bytes - the screening itself is covered in test_document_validation.py.
"""

import io
from decimal import Decimal

from sqlalchemy import select


async def _customer_quote(db_session, provider, phone, total="30000.00"):
    from app.models.customer import Customer
    from app.models.quote import Quote, QuoteRequest

    customer = Customer(full_name="Reuse Tester", phone=phone)
    db_session.add(customer)
    await db_session.flush()
    qr = QuoteRequest(
        reference=f"SOM-2026-{phone[-6:]}",
        customer_id=customer.id,
        category="motor",
        input_data={"registration_number": "KDA 123X", "make": "Toyota", "model": "Axio", "year": 2015},
        status="quoted",
    )
    db_session.add(qr)
    await db_session.flush()
    quote = Quote(
        quote_request_id=qr.id, provider_id=provider.id, premium=Decimal("25862.00"), taxes=Decimal("4137.92"),
        fees=Decimal("0.08"), total=Decimal(total), currency="KES", is_mock=True, status="available",
    )
    db_session.add(quote)
    await db_session.commit()
    return customer, quote


async def _upload(client, application_id, doc_type):
    return await client.post(
        f"/api/v1/applications/{application_id}/documents",
        params={"document_type": doc_type},
        files={"file": (f"{doc_type}.pdf", io.BytesIO(b"%PDF-1.4 placeholder"), "application/pdf")},
    )


# --- availability / coming soon ---------------------------------------------


async def test_categories_with_only_demo_insurers_are_coming_soon(client, seeded_providers):
    res = await client.get("/api/v1/quotes/availability")
    assert res.status_code == 200
    categories = res.json()["categories"]
    # Only mock providers are seeded in tests, so nothing has live pricing.
    assert categories["medical"] == {"available": False, "mode": "coming_soon"}
    assert categories["motor"]["available"] is False


async def test_demo_categories_can_be_allowed_for_staging(client, seeded_providers, monkeypatch):
    from app.services import quote_availability

    class _Settings:
        allow_demo_quote_categories = True

    monkeypatch.setattr(quote_availability, "get_settings", lambda: _Settings())
    categories = (await client.get("/api/v1/quotes/availability")).json()["categories"]
    assert categories["medical"] == {"available": True, "mode": "demo"}


async def test_posting_a_quote_for_a_coming_soon_category_still_works_for_existing_callers(client, seeded_providers):
    res = await client.post(
        "/api/v1/quotes", json={"category": "medical", "answers": {"phone": "0700555666", "full_name": "Direct API"}}
    )
    assert res.status_code == 200  # the availability gate is a UI concern; the engine is unchanged


# --- document requirements ----------------------------------------------------


async def test_document_requirements_list_what_to_prepare(client):
    motor = (await client.get("/api/v1/quotes/document-requirements", params={"category": "motor"})).json()
    assert [d["type"] for d in motor["insurance"]] == ["national_id", "logbook", "kra_pin"]
    assert motor["max_mb"] == 10

    medical = (await client.get("/api/v1/quotes/document-requirements", params={"category": "medical"})).json()
    assert [d["type"] for d in medical["insurance"]] == ["national_id", "kra_pin"]  # no logbook for medical

    corporate = (
        await client.get("/api/v1/quotes/document-requirements", params={"category": "motor", "corporate": "true"})
    ).json()
    fin_types = [d["type"] for d in corporate["financing"]["documents"]]
    assert "certificate_of_incorporation" in fin_types and "national_id" not in fin_types


# --- application status -----------------------------------------------------


async def test_application_status_exposes_status_only(client, db_session, seeded_providers):
    customer, quote = await _customer_quote(db_session, seeded_providers[0], "0788100001")
    app_res = await client.post(
        "/api/v1/applications",
        json={"quote_id": str(quote.id), "customer_id": str(customer.id), "applicant_details": {}},
    )
    application = app_res.json()

    res = await client.get(f"/api/v1/applications/{application['id']}/status")
    assert res.status_code == 200
    assert set(res.json()) == {"id", "reference", "status"}
    assert (await client.get("/api/v1/applications/00000000-0000-0000-0000-000000000000/status")).status_code == 404


# --- financing document reuse -------------------------------------------------


async def test_financing_reuses_insurance_documents_and_generates_the_premium_quote(client, db_session, seeded_providers):
    customer, quote = await _customer_quote(db_session, seeded_providers[0], "0788100002")
    application = (
        await client.post(
            "/api/v1/applications",
            json={"quote_id": str(quote.id), "customer_id": str(customer.id), "applicant_details": {}},
        )
    ).json()
    for doc_type in ("national_id", "logbook", "kra_pin"):
        assert (await _upload(client, application["id"], doc_type)).status_code == 200

    fin = (
        await client.post(
            "/api/v1/financing/applications",
            json={"customer_id": str(customer.id), "quote_id": str(quote.id), "term_months": 6},
        )
    ).json()

    # read-only checklist changes nothing
    before = (await client.get(f"/api/v1/financing/applications/{fin['id']}/documents/checklist")).json()
    assert set(before["missing"]) == {"application_form", "logbook", "national_id", "kra_pin"}

    prepared = (await client.post(f"/api/v1/financing/applications/{fin['id']}/documents/prepare")).json()
    states = {i["type"]: (i["state"], i["source"]) for i in prepared["items"]}
    assert states["logbook"] == ("provided", "insurance_application")
    assert states["national_id"] == ("provided", "insurance_application")
    assert states["kra_pin"] == ("provided", "insurance_application")
    assert states["premium_quote"] == ("provided", "generated")
    assert prepared["missing"] == ["application_form"]  # the only thing the customer still has to supply
    assert prepared["complete"] is False

    # idempotent: calling again doesn't attach duplicates
    again = (await client.post(f"/api/v1/financing/applications/{fin['id']}/documents/prepare")).json()
    assert again["missing"] == ["application_form"]
    from app.models.financing import FinancingDocument

    docs = (await db_session.scalars(select(FinancingDocument).where(FinancingDocument.financing_application_id == fin["id"]))).all()
    assert sorted(d.document_type for d in docs) == ["kra_pin", "logbook", "national_id", "premium_quote"]


async def test_guest_does_not_get_documents_reused_from_other_applications(client, db_session, seeded_providers):
    """Cross-application reuse needs a logged-in customer: a guest is only
    identified by phone number, so someone else's old ID must never be
    attached to a new application just because the phone matches."""
    customer, quote_one = await _customer_quote(db_session, seeded_providers[0], "0788100003")
    first = (
        await client.post(
            "/api/v1/applications",
            json={"quote_id": str(quote_one.id), "customer_id": str(customer.id), "applicant_details": {}},
        )
    ).json()
    await _upload(client, first["id"], "national_id")

    from app.models.quote import Quote, QuoteRequest

    qr = QuoteRequest(reference="SOM-2026-100033", customer_id=customer.id, category="motor", status="quoted")
    db_session.add(qr)
    await db_session.flush()
    quote_two = Quote(
        quote_request_id=qr.id, provider_id=seeded_providers[0].id, premium=Decimal("1000"), taxes=Decimal("0"),
        fees=Decimal("0"), total=Decimal("1000"), currency="KES", is_mock=True, status="available",
    )
    db_session.add(quote_two)
    await db_session.commit()

    second = (
        await client.post(
            "/api/v1/applications",
            json={"quote_id": str(quote_two.id), "customer_id": str(customer.id), "applicant_details": {}},
        )
    ).json()
    prepared = (await client.post(f"/api/v1/applications/{second['id']}/documents/prepare")).json()  # no token
    assert set(prepared["missing"]) == {"national_id", "logbook", "kra_pin"}


# --- agent callback + eligibility context -------------------------------------


async def test_agent_callback_request_tags_the_lead_with_the_product(client, db_session):
    from app.models.crm import Lead
    from app.models.customer import Customer

    res = await client.post(
        "/api/v1/contact",
        json={
            "full_name": "Wanjiru", "phone": "0700777888", "message": "Please call me about medical cover",
            "product_interest": "medical",
        },
    )
    assert res.status_code == 200
    customer = await db_session.scalar(select(Customer).where(Customer.phone == "0700777888"))
    lead = await db_session.scalar(select(Lead).where(Lead.customer_id == customer.id))
    assert lead.product_interest == "medical"


async def test_eligibility_includes_settings_context_for_the_ui(client, db_session, seeded_providers):
    customer, quote = await _customer_quote(db_session, seeded_providers[0], "0788100004")
    body = (
        await client.post(
            "/api/v1/financing/eligibility",
            json={"customer_id": str(customer.id), "quote_id": str(quote.id), "term_months": 6},
        )
    ).json()
    assert body["min_term_months"] == 4 and body["max_term_months"] == 10
    assert body["concession_loan_age_max_months"] == 3
    assert Decimal(body["standard_interest_rate_monthly"]) == Decimal("3.50")
    assert Decimal(body["preferred_interest_rate_monthly"]) == Decimal("3.00")
    assert Decimal(body["standard_deposit_percentage"]) == Decimal("20.00")


# --- phone matching ----------------------------------------------------------


def test_phone_variants_cover_the_common_kenyan_spellings():
    from app.core.phone import phone_variants

    expected = {"0712345678", "254712345678", "+254712345678"}
    for typed in ("0712 345 678", "+254712345678", "254712345678", "0712-345-678", "712345678"):
        assert expected <= set(phone_variants(typed)), typed
    assert phone_variants("") == [] and phone_variants(None) == []
    assert phone_variants("12345") == ["12345"]  # unusual numbers still match exactly


async def test_same_person_typing_their_number_differently_is_one_customer(client, db_session, seeded_providers):
    from app.models.customer import Customer

    first = await client.post(
        "/api/v1/quotes", json={"category": "medical", "answers": {"phone": "0722333444", "full_name": "Phone Tester"}}
    )
    second = await client.post(
        "/api/v1/quotes", json={"category": "medical", "answers": {"phone": "+254722333444", "full_name": "Phone Tester"}}
    )
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["customer_id"] == second.json()["customer_id"]
    rows = (await db_session.scalars(select(Customer).where(Customer.full_name == "Phone Tester"))).all()
    assert len(rows) == 1 and rows[0].phone == "0722333444"  # stored exactly as first typed


# --- zero-deposit financing -> staff task ---------------------------------------


async def test_zero_deposit_approval_creates_one_staff_task(client, db_session, seeded_providers):
    from app.models.crm import Task

    customer, quote = await _customer_quote(db_session, seeded_providers[0], "0788100005")
    fin = (
        await client.post(
            "/api/v1/financing/applications",
            json={
                "customer_id": str(customer.id), "quote_id": str(quote.id), "term_months": 6,
                "has_existing_logbook_loan": True, "logbook_loan_age_months": 1,
            },
        )
    ).json()
    if fin["status"] != "approved":  # the mock credit provider decides - only meaningful when approved
        return
    assert Decimal(fin["deposit_amount"]) == 0
    tasks = (await db_session.scalars(select(Task).where(Task.title.contains(fin["reference"])))).all()
    assert len(tasks) == 1 and tasks[0].status == "open"


async def test_a_deposit_paying_approval_creates_no_task(client, db_session, seeded_providers):
    from app.models.crm import Task

    customer, quote = await _customer_quote(db_session, seeded_providers[0], "0788100006")
    fin = (
        await client.post(
            "/api/v1/financing/applications",
            json={"customer_id": str(customer.id), "quote_id": str(quote.id), "term_months": 6},
        )
    ).json()
    assert Decimal(fin["deposit_amount"]) > 0
    assert (await db_session.scalars(select(Task).where(Task.title.contains(fin["reference"])))).all() == []


# --- company terms ----------------------------------------------------------------


async def test_company_terms_apply_only_when_management_sets_them(client, db_session, seeded_providers, monkeypatch):
    from app.models.financing import FinancingSettings
    from app.services.financing_service import get_financing_settings

    customer, quote = await _customer_quote(db_session, seeded_providers[0], "0788100007")
    body = {"customer_id": str(customer.id), "quote_id": str(quote.id), "term_months": 6, "is_corporate": True}

    unset = (await client.post("/api/v1/financing/eligibility", json=body)).json()
    assert unset["corporate_terms_applied"] is False
    assert Decimal(unset["deposit_percentage"]) == Decimal("20.00")  # blank = same as standard

    settings = await get_financing_settings(db_session)
    settings.corporate_deposit_percentage = Decimal("30.00")
    settings.corporate_interest_rate_monthly = Decimal("4.00")
    await db_session.commit()

    company = (await client.post("/api/v1/financing/eligibility", json=body)).json()
    assert company["corporate_terms_applied"] is True
    assert Decimal(company["deposit_percentage"]) == Decimal("30.00")
    assert Decimal(company["interest_rate_monthly"]) == Decimal("4.00")

    individual = (await client.post("/api/v1/financing/eligibility", json={**body, "is_corporate": False})).json()
    assert individual["corporate_terms_applied"] is False
    assert Decimal(individual["deposit_percentage"]) == Decimal("20.00")

    # the existing-customer concession still wins over company terms
    concession = (
        await client.post(
            "/api/v1/financing/eligibility",
            json={**body, "has_existing_logbook_loan": True, "logbook_loan_age_months": 1},
        )
    ).json()
    assert concession["concession_applied"] is True and concession["corporate_terms_applied"] is False

    # restore the singleton so other tests see the defaults
    settings.corporate_deposit_percentage = None
    settings.corporate_interest_rate_monthly = None
    await db_session.commit()


# --- product catalogue: property replaces home & business; cargo/hull/cyber are coming soon ---


async def test_coming_soon_products_are_never_quotable_even_in_demo_mode(client, seeded_providers, monkeypatch):
    from app.services import quote_availability

    class _Settings:
        allow_demo_quote_categories = True

    monkeypatch.setattr(quote_availability, "get_settings", lambda: _Settings())
    categories = (await client.get("/api/v1/quotes/availability")).json()["categories"]
    for category in ("cargo", "hull", "cybersecurity"):
        assert categories[category] == {"available": False, "mode": "coming_soon"}
    assert categories["property"] == {"available": True, "mode": "demo"}  # demo insurers price it
    assert "home" not in categories and "business" not in categories


async def test_the_quote_api_refuses_coming_soon_products(client, seeded_providers):
    for category in ("cargo", "hull", "cybersecurity"):
        res = await client.post("/api/v1/quotes", json={"category": category, "answers": {"phone": "0700111000"}})
        assert res.status_code == 422
        assert "coming soon" in res.json()["detail"]


async def test_property_quotes_respond_to_the_cover_options_chosen(client, seeded_providers):
    def body(options):
        return {
            "category": "property",
            "answers": {
                "phone": "0700222000", "full_name": "Property Tester", "sum_insured": "5000000",
                "property_use": "home", "cover_options": options,
            },
        }

    fire_only = (await client.post("/api/v1/quotes", json=body(["fire"]))).json()
    fire_theft = (await client.post("/api/v1/quotes", json=body(["fire", "theft_burglary"]))).json()
    assert fire_only["category"] == "property" and fire_only["quotes"] and fire_theft["quotes"]
    cheapest = lambda result: min(float(q["premium"]) for q in result["quotes"])  # noqa: E731
    assert cheapest(fire_theft) > cheapest(fire_only)
    assert all("Theft & burglary" in q["coverage"]["summary"] for q in fire_theft["quotes"])


async def test_old_home_and_business_requests_are_served_as_property(client, seeded_providers):
    for legacy in ("home", "business"):
        res = await client.post(
            "/api/v1/quotes", json={"category": legacy, "answers": {"phone": "0700333000", "full_name": "Legacy Client"}}
        )
        assert res.status_code == 200
        assert res.json()["category"] == "property"


async def test_property_applicants_are_asked_for_proof_of_ownership_not_a_logbook(client):
    props = (await client.get("/api/v1/quotes/document-requirements", params={"category": "property"})).json()
    assert [d["type"] for d in props["insurance"]] == ["national_id", "property_proof", "kra_pin"]
    legacy = (await client.get("/api/v1/quotes/document-requirements", params={"category": "home"})).json()
    assert [d["type"] for d in legacy["insurance"]] == ["national_id", "property_proof", "kra_pin"]
