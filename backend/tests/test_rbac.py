import uuid

from sqlalchemy import select


async def _register_and_assign_role(client, db_session, email, password, role_name):
    """Registers a normal account then reassigns its role directly in the
    DB - the registration endpoint always assigns 'customer', and there's
    no public signup path for staff roles (correctly so)."""
    from app.models.user import Role, User, UserRole

    await client.post("/api/v1/auth/register", json={"full_name": "Staff Test", "email": email, "password": password})
    user = await db_session.scalar(select(User).where(User.email == email))

    role = await db_session.scalar(select(Role).where(Role.name == role_name))
    if not role:
        role = Role(id=uuid.uuid4(), name=role_name)
        db_session.add(role)
        await db_session.flush()

    await db_session.execute(UserRole.__table__.delete().where(UserRole.user_id == user.id))
    db_session.add(UserRole(user_id=user.id, role_id=role.id))
    await db_session.commit()

    login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return login.json()["access_token"]


async def test_customer_cannot_access_admin_providers(client, db_session):
    await client.post("/api/v1/auth/register", json={"full_name": "Plain Customer", "email": "plain@example.com", "password": "supersecret1"})
    login = await client.post("/api/v1/auth/login", json={"email": "plain@example.com", "password": "supersecret1"})
    token = login.json()["access_token"]

    res = await client.get("/api/v1/admin/providers", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


async def test_super_admin_can_access_admin_providers(client, db_session):
    token = await _register_and_assign_role(client, db_session, "admin@example.com", "supersecret1", "super_admin")

    res = await client.get("/api/v1/admin/providers", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200


async def test_no_token_is_rejected_not_silently_allowed(client):
    res = await client.get("/api/v1/admin/providers")
    assert res.status_code == 401


async def test_sales_agent_can_view_leads_but_not_admin_providers(client, db_session):
    token = await _register_and_assign_role(client, db_session, "agent@example.com", "supersecret1", "sales_agent")

    leads_res = await client.get("/api/v1/admin/leads", headers={"Authorization": f"Bearer {token}"})
    assert leads_res.status_code == 200

    providers_res = await client.get("/api/v1/admin/providers", headers={"Authorization": f"Bearer {token}"})
    assert providers_res.status_code == 403, "sales_agent should not have provider-management access"


async def test_underwriter_can_approve_application(client, db_session, seeded_providers):
    import io

    from app.models.customer import Customer

    # Create a real application to approve
    await client.post("/api/v1/quotes", json={"category": "motor", "answers": {"owner_phone": "0799888777", "owner_name": "RBAC Test"}})
    customer = await db_session.scalar(select(Customer).where(Customer.phone == "0799888777"))

    quote_res = await client.post("/api/v1/quotes", json={"category": "motor", "answers": {"owner_phone": "0799888777", "owner_name": "RBAC Test"}})
    quote = quote_res.json()["quotes"][0]

    app_res = await client.post(
        "/api/v1/applications", json={"quote_id": quote["id"], "customer_id": str(customer.id), "applicant_details": {}}
    )
    application_id = app_res.json()["id"]
    await client.post(
        f"/api/v1/applications/{application_id}/documents",
        params={"document_type": "national_id"},
        files={"file": ("id.pdf", io.BytesIO(b"fake"), "application/pdf")},
    )
    await client.post(f"/api/v1/applications/{application_id}/submit")

    token = await _register_and_assign_role(client, db_session, "underwriter@example.com", "supersecret1", "underwriter")
    res = await client.post(f"/api/v1/admin/applications/{application_id}/approve", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["status"] == "approved"
