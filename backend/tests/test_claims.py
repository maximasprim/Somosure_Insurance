import io
from datetime import date

from sqlalchemy import select


async def _create_active_policy(db_session, seeded_providers, phone="0700555111"):
    from app.models.application import Application
    from app.models.customer import Customer
    from app.models.policy import Policy
    from app.models.quote import Quote, QuoteRequest

    customer = Customer(full_name="Claims Test", phone=phone)
    db_session.add(customer)
    await db_session.flush()

    qr = QuoteRequest(reference=f"SOM-2026-{phone[-6:]}", customer_id=customer.id, category="motor", status="quoted")
    db_session.add(qr)
    await db_session.flush()

    from decimal import Decimal

    quote = Quote(
        quote_request_id=qr.id, provider_id=seeded_providers[0].id, premium=Decimal("18000"), taxes=Decimal("2880"),
        fees=Decimal("500"), total=Decimal("21380"), currency="KES", is_mock=True, status="selected",
    )
    db_session.add(quote)
    await db_session.flush()

    application = Application(reference=f"SOM-APP-2026-{phone[-6:]}", quote_id=quote.id, customer_id=customer.id, status="approved")
    db_session.add(application)
    await db_session.flush()

    policy = Policy(
        policy_number=f"MOCK-POL-{phone[-6:]}", application_id=application.id, provider_id=seeded_providers[0].id,
        customer_id=customer.id, start_date=date.today(), end_date=date(date.today().year + 1, date.today().month, date.today().day),
        premium=Decimal("21380"), payment_status="successful", status="active", is_mock=True,
    )
    db_session.add(policy)
    await db_session.commit()
    return customer, policy


async def test_report_claim_against_active_policy(client, db_session, seeded_providers):
    customer, policy = await _create_active_policy(db_session, seeded_providers)

    res = await client.post(
        "/api/v1/claims",
        json={
            "policy_id": str(policy.id),
            "customer_id": str(customer.id),
            "incident_date": "2026-08-01",
            "incident_description": "Rear-ended at a junction, minor bumper damage.",
            "incident_location": "Nairobi",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["reference"].startswith("SOM-CLM-")
    assert body["status"] == "reported"


async def test_cannot_claim_against_someone_elses_policy(client, db_session, seeded_providers):
    from app.models.customer import Customer

    customer, policy = await _create_active_policy(db_session, seeded_providers, phone="0700555222")
    other_customer = Customer(full_name="Someone Else", phone="0700555333")
    db_session.add(other_customer)
    await db_session.commit()

    res = await client.post(
        "/api/v1/claims",
        json={
            "policy_id": str(policy.id),
            "customer_id": str(other_customer.id),
            "incident_date": "2026-08-01",
            "incident_description": "Trying to claim on someone else's policy.",
        },
    )
    assert res.status_code == 403


async def test_claim_upload_and_submit_flow(client, db_session, seeded_providers):
    customer, policy = await _create_active_policy(db_session, seeded_providers, phone="0700555444")

    report_res = await client.post(
        "/api/v1/claims",
        json={
            "policy_id": str(policy.id), "customer_id": str(customer.id),
            "incident_date": "2026-08-01", "incident_description": "Windscreen cracked by a stone.",
        },
    )
    claim_id = report_res.json()["id"]

    # Cannot submit without at least one document
    early_submit = await client.post(f"/api/v1/claims/{claim_id}/submit")
    assert early_submit.status_code == 400

    upload_res = await client.post(
        f"/api/v1/claims/{claim_id}/documents",
        params={"document_type": "incident_photo"},
        files={"file": ("damage.jpg", io.BytesIO(b"fake jpeg bytes"), "image/jpeg")},
    )
    assert upload_res.status_code == 200

    # MockProvider's submit_claim() succeeds (it's a working mock, unlike
    # the pending real-insurer adapters which raise NotImplementedError),
    # so this correctly takes the "provider accepted the claim" path.
    submit_res = await client.post(f"/api/v1/claims/{claim_id}/submit")
    assert submit_res.status_code == 200
    assert submit_res.json()["status"] == "under_review"
    assert submit_res.json()["provider_reference"] is not None, "a successful provider submission should record its reference"


async def test_claim_falls_back_to_staff_assisted_when_provider_has_no_claims_api(client, db_session, seeded_providers):
    """A policy underwritten by a real (pending-integration) insurer should
    fall back to staff-assisted claim processing, not crash, when that
    adapter's submit_claim() raises NotImplementedError."""
    import uuid
    from decimal import Decimal

    from app.models.application import Application
    from app.models.customer import Customer
    from app.models.policy import Policy
    from app.models.provider import InsuranceProvider
    from app.models.quote import Quote, QuoteRequest

    britam = InsuranceProvider(
        id=uuid.uuid4(), name="Britam", provider_type="insurer", integration_mode="rest",
        status="active", supports_quote=False, integration_version="pending",
    )
    db_session.add(britam)
    await db_session.flush()

    customer = Customer(full_name="Fallback Test", phone="0700555666")
    db_session.add(customer)
    await db_session.flush()

    qr = QuoteRequest(reference="SOM-2026-555666", customer_id=customer.id, category="motor", status="quoted")
    db_session.add(qr)
    await db_session.flush()

    quote = Quote(quote_request_id=qr.id, provider_id=britam.id, premium=Decimal("18000"), taxes=Decimal("2880"), fees=Decimal("500"), total=Decimal("21380"), currency="KES", is_mock=False, status="selected")
    db_session.add(quote)
    await db_session.flush()

    application = Application(reference="SOM-APP-2026-555666", quote_id=quote.id, customer_id=customer.id, status="approved")
    db_session.add(application)
    await db_session.flush()

    policy = Policy(
        policy_number="BRITAM-POL-000001", application_id=application.id, provider_id=britam.id, customer_id=customer.id,
        start_date=date.today(), end_date=date(date.today().year + 1, 1, 1), premium=Decimal("21380"),
        payment_status="successful", status="active", is_mock=False,
    )
    db_session.add(policy)
    await db_session.commit()

    report_res = await client.post(
        "/api/v1/claims",
        json={"policy_id": str(policy.id), "customer_id": str(customer.id), "incident_date": "2026-08-01", "incident_description": "Real insurer, no claims API yet."},
    )
    claim_id = report_res.json()["id"]

    await client.post(
        f"/api/v1/claims/{claim_id}/documents",
        params={"document_type": "incident_photo"},
        files={"file": ("damage.jpg", io.BytesIO(b"fake"), "image/jpeg")},
    )

    submit_res = await client.post(f"/api/v1/claims/{claim_id}/submit")
    assert submit_res.status_code == 200
    assert submit_res.json()["status"] == "submitted", "should fall back to staff-assisted, not crash or silently fabricate a provider response"
    assert submit_res.json()["provider_reference"] is None


async def test_staff_can_transition_claim_through_valid_states_only(client, db_session, seeded_providers):
    import uuid

    from app.models.claim import Claim, ClaimEvent
    from app.models.user import Role, User, UserRole
    from app.core.security import hash_password

    customer, policy = await _create_active_policy(db_session, seeded_providers, phone="0700555555")

    claim = Claim(
        reference="SOM-CLM-2026-000001", policy_id=policy.id, customer_id=customer.id,
        incident_date=date.today(), incident_description="Test claim for staff transitions.", status="submitted",
    )
    db_session.add(claim)
    await db_session.commit()

    user = User(email="claimsofficer@example.com", full_name="Claims Officer", hashed_password=hash_password("supersecret1"))
    db_session.add(user)
    await db_session.flush()
    role = Role(id=uuid.uuid4(), name="claims_officer")
    db_session.add(role)
    await db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id=role.id))
    await db_session.commit()

    login = await client.post("/api/v1/auth/login", json={"email": "claimsofficer@example.com", "password": "supersecret1"})
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Valid: submitted -> under_review
    res1 = await client.post(f"/api/v1/admin/claims/{claim.id}/transition", json={"to_status": "under_review"}, headers=headers)
    assert res1.status_code == 200
    assert res1.json()["status"] == "under_review"

    # Invalid: cannot skip straight to "settled" from under_review
    res2 = await client.post(f"/api/v1/admin/claims/{claim.id}/transition", json={"to_status": "settled"}, headers=headers)
    assert res2.status_code == 409

    # Valid: under_review -> approved -> settled
    await client.post(f"/api/v1/admin/claims/{claim.id}/transition", json={"to_status": "approved"}, headers=headers)
    res3 = await client.post(f"/api/v1/admin/claims/{claim.id}/transition", json={"to_status": "settled"}, headers=headers)
    assert res3.status_code == 200
    assert res3.json()["status"] == "settled"

    events = (await db_session.scalars(select(ClaimEvent).where(ClaimEvent.claim_id == claim.id))).all()
    assert len(events) == 3  # under_review, approved, settled transitions all logged
