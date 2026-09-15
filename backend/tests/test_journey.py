import io

from sqlalchemy import select


async def _get_a_quote(client, seeded_providers, phone="0700000001"):
    res = await client.post("/api/v1/quotes", json={"category": "motor", "answers": {"owner_phone": phone, "owner_name": "Journey Test"}})
    body = res.json()
    quote = body["quotes"][0]
    return body, quote


async def test_full_journey_quote_to_policy_issuance(client, db_session, seeded_providers, seeded_automation_rules):
    """The whole customer-facing spine of the platform in one test:
    quote -> application -> document upload -> submit -> underwriting
    approval -> M-Pesa payment (initiate + signed webhook) -> automatic
    policy issuance -> sticker auto-generated via the automation engine.
    """
    from app.models.customer import Customer

    _, quote = await _get_a_quote(client, seeded_providers)
    customer_id = quote["provider_id"]  # placeholder, replaced below
    # Fetch the actual customer created by the guest quote flow.
    customer = await db_session.scalar(select(Customer).where(Customer.phone == "0700000001"))
    assert customer is not None

    # 1. Create an application from the quote
    app_res = await client.post(
        "/api/v1/applications",
        json={"quote_id": quote["id"], "customer_id": str(customer.id), "applicant_details": {}},
    )
    assert app_res.status_code == 200
    application = app_res.json()
    assert application["status"] == "draft"

    # 2. Upload a document
    doc_res = await client.post(
        f"/api/v1/applications/{application['id']}/documents",
        params={"document_type": "national_id"},
        files={"file": ("id.pdf", io.BytesIO(b"%PDF-1.4 fake pdf content"), "application/pdf")},
    )
    assert doc_res.status_code == 200
    assert doc_res.json()["status"] == "uploaded"

    # 3. Submit the application
    submit_res = await client.post(f"/api/v1/applications/{application['id']}/submit")
    assert submit_res.status_code == 200
    assert submit_res.json()["status"] == "submitted"

    # 4. Staff approves (requires an authenticated staff role - registering
    # a plain customer account won't have underwriter/ops/admin rights, so
    # this step is exercised directly via the service layer in
    # test_rbac.py; here we approve via direct DB manipulation to keep this
    # test focused on the payment -> issuance -> automation chain).
    from app.services.application_service import approve_application

    await approve_application(db_session, application["id"])

    # 5. Initiate payment
    pay_res = await client.post(
        "/api/v1/payments/initiate",
        json={
            "application_id": application["id"],
            "customer_id": str(customer.id),
            "amount": quote["total"],
            "phone": "0700000001",
            "method": "mpesa",
        },
    )
    assert pay_res.status_code == 200
    payment = pay_res.json()
    assert payment["status"] == "pending"

    # 6. Simulate the customer completing the M-Pesa prompt - goes through
    # the REAL signed-webhook verification path, not a shortcut.
    sim_res = await client.post(
        f"/api/v1/payments/{payment['provider_transaction_id']}/simulate-completion",
        params={"outcome": "successful", "amount": quote["total"]},
    )
    assert sim_res.status_code == 200
    assert sim_res.json()["status"] == "successful"

    # 7. Policy should now be issued automatically
    from app.models.policy import Policy

    policy = await db_session.scalar(select(Policy).where(Policy.application_id == application["id"]))
    assert policy is not None
    assert policy.status == "active"
    assert policy.is_mock is True

    # 8. A sticker should have been auto-generated via the automation
    # engine's "policy.activated" -> generate_sticker rule for motor -
    # but automation runs are SCHEDULED, not executed inline. Run the due
    # automations to actually fire it.
    from app.automation.engine import run_due_automations

    result = await run_due_automations(db_session)
    assert result["executed"] >= 1

    from app.models.sticker import Sticker

    sticker = await db_session.scalar(select(Sticker).where(Sticker.policy_id == policy.id))
    assert sticker is not None
    assert sticker.status == "pending"
    assert sticker.reference.startswith("SOM-STK-")


async def test_webhook_rejects_invalid_signature(client):
    """The backend must never trust a payment callback without a valid
    signature - this is the core spec §13 rule, tested directly."""
    res = await client.post(
        "/api/v1/webhooks/mpesa",
        headers={"X-Mock-Signature": "not-a-real-signature"},
        content=b'{"CheckoutRequestID": "FAKE-123", "ResultCode": 0, "Amount": "1000"}',
    )
    assert res.status_code == 401


async def test_duplicate_webhook_callback_is_idempotent(client, db_session, seeded_providers):
    """A payment already marked successful must not be processed twice -
    prevents double policy issuance from a duplicate provider callback."""
    from app.models.customer import Customer

    _, quote = await _get_a_quote(client, seeded_providers, phone="0700000002")
    customer = await db_session.scalar(select(Customer).where(Customer.phone == "0700000002"))

    app_res = await client.post(
        "/api/v1/applications", json={"quote_id": quote["id"], "customer_id": str(customer.id), "applicant_details": {}}
    )
    application = app_res.json()
    await client.post(
        f"/api/v1/applications/{application['id']}/documents",
        params={"document_type": "national_id"},
        files={"file": ("id.pdf", io.BytesIO(b"fake"), "application/pdf")},
    )
    await client.post(f"/api/v1/applications/{application['id']}/submit")

    from app.services.application_service import approve_application

    await approve_application(db_session, application["id"])

    pay_res = await client.post(
        "/api/v1/payments/initiate",
        json={"application_id": application["id"], "customer_id": str(customer.id), "amount": quote["total"], "phone": "0700000002"},
    )
    payment = pay_res.json()

    first = await client.post(
        f"/api/v1/payments/{payment['provider_transaction_id']}/simulate-completion",
        params={"outcome": "successful", "amount": quote["total"]},
    )
    assert first.json()["status"] == "successful"

    second = await client.post(
        f"/api/v1/payments/{payment['provider_transaction_id']}/simulate-completion",
        params={"outcome": "successful", "amount": quote["total"]},
    )
    assert second.json()["status"] == "already_processed"

    from app.models.policy import Policy

    policies = (await db_session.scalars(select(Policy).where(Policy.application_id == application["id"]))).all()
    assert len(policies) == 1, "a duplicate webhook must not issue a second policy"
