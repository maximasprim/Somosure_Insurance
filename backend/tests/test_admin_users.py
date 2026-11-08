"""Admin editing of user details and passwords (/api/v1/admin/users)."""

import uuid

from sqlalchemy import select


async def _make_user(client, db_session, email, password, role_name, full_name="Test User"):
    """Registers an account, then moves it to `role_name` directly in the DB
    (registration always assigns 'customer'). Returns (user, access_token)."""
    from app.models.user import Role, User, UserRole

    await client.post("/api/v1/auth/register", json={"full_name": full_name, "email": email, "password": password})
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
    return user, login.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def test_super_admin_can_edit_name_email_and_phone(client, db_session):
    _, admin_token = await _make_user(client, db_session, "boss@example.com", "supersecret1", "super_admin")
    target, _ = await _make_user(client, db_session, "target@example.com", "supersecret1", "customer", "Old Name")

    res = await client.patch(
        f"/api/v1/admin/users/{target.id}",
        json={"full_name": "New Name", "email": "renamed@example.com", "phone": "0711222333"},
        headers=_auth(admin_token),
    )
    assert res.status_code == 200
    body = res.json()
    assert body["full_name"] == "New Name"
    assert body["email"] == "renamed@example.com"
    assert body["phone"] == "0711222333"
    assert body["role"] == "customer", "editing details must not touch the role"

    # The customer profile the user sees on their own dashboard follows along.
    from app.models.customer import Customer

    db_session.expire_all()
    customer = await db_session.scalar(select(Customer).where(Customer.user_id == target.id))
    assert customer.full_name == "New Name"
    assert customer.email == "renamed@example.com"
    assert customer.phone == "0711222333"

    # And they can sign in with the new email.
    login = await client.post("/api/v1/auth/login", json={"email": "renamed@example.com", "password": "supersecret1"})
    assert login.status_code == 200


async def test_email_must_be_unique_ignoring_case(client, db_session):
    _, admin_token = await _make_user(client, db_session, "boss@example.com", "supersecret1", "super_admin")
    target, _ = await _make_user(client, db_session, "target@example.com", "supersecret1", "customer")
    await _make_user(client, db_session, "taken@example.com", "supersecret1", "customer")

    res = await client.patch(
        f"/api/v1/admin/users/{target.id}", json={"email": "TAKEN@example.com"}, headers=_auth(admin_token)
    )
    assert res.status_code == 409


async def test_phone_can_be_cleared_and_blank_name_is_refused(client, db_session):
    _, admin_token = await _make_user(client, db_session, "boss@example.com", "supersecret1", "super_admin")
    target, _ = await _make_user(client, db_session, "target@example.com", "supersecret1", "customer")

    await client.patch(f"/api/v1/admin/users/{target.id}", json={"phone": "0700111222"}, headers=_auth(admin_token))
    cleared = await client.patch(f"/api/v1/admin/users/{target.id}", json={"phone": None}, headers=_auth(admin_token))
    assert cleared.status_code == 200
    assert cleared.json()["phone"] is None

    blank = await client.patch(f"/api/v1/admin/users/{target.id}", json={"full_name": " "}, headers=_auth(admin_token))
    assert blank.status_code == 400


async def test_existing_role_and_active_toggles_still_work(client, db_session):
    _, admin_token = await _make_user(client, db_session, "boss@example.com", "supersecret1", "super_admin")
    await _make_user(client, db_session, "agent@example.com", "supersecret1", "sales_agent")  # makes sure the role exists
    target, _ = await _make_user(client, db_session, "target@example.com", "supersecret1", "customer")

    res = await client.patch(
        f"/api/v1/admin/users/{target.id}", json={"role": "sales_agent", "is_active": False}, headers=_auth(admin_token)
    )
    assert res.status_code == 200
    assert res.json()["role"] == "sales_agent"
    assert res.json()["is_active"] is False


async def test_admin_cannot_demote_or_deactivate_themselves(client, db_session):
    admin, admin_token = await _make_user(client, db_session, "boss@example.com", "supersecret1", "super_admin")

    res = await client.patch(
        f"/api/v1/admin/users/{admin.id}", json={"is_active": False}, headers=_auth(admin_token)
    )
    assert res.status_code == 400

    # Editing their own contact details is fine.
    ok = await client.patch(f"/api/v1/admin/users/{admin.id}", json={"phone": "0700999888"}, headers=_auth(admin_token))
    assert ok.status_code == 200


async def test_reset_password_changes_login_and_cancels_pending_reset_links(client, db_session):
    _, admin_token = await _make_user(client, db_session, "boss@example.com", "supersecret1", "super_admin")
    target, _ = await _make_user(client, db_session, "target@example.com", "oldpassword1", "customer")

    # The user had asked for a reset email earlier.
    await client.post("/api/v1/auth/forgot-password", json={"email": "target@example.com"})

    res = await client.post(
        f"/api/v1/admin/users/{target.id}/reset-password",
        json={"new_password": "brandnewpass9"},
        headers={**_auth(admin_token), "X-Audit-Reason": "Customer called and lost access"},
    )
    assert res.status_code == 204

    old = await client.post("/api/v1/auth/login", json={"email": "target@example.com", "password": "oldpassword1"})
    assert old.status_code == 401
    new = await client.post("/api/v1/auth/login", json={"email": "target@example.com", "password": "brandnewpass9"})
    assert new.status_code == 200

    from app.models.password_reset_token import PasswordResetToken

    db_session.expire_all()
    tokens = (await db_session.scalars(select(PasswordResetToken).where(PasswordResetToken.user_id == target.id))).all()
    assert tokens and all(t.used_at is not None for t in tokens)


async def test_reset_password_validates_and_404s(client, db_session):
    _, admin_token = await _make_user(client, db_session, "boss@example.com", "supersecret1", "super_admin")
    target, _ = await _make_user(client, db_session, "target@example.com", "oldpassword1", "customer")

    short = await client.post(
        f"/api/v1/admin/users/{target.id}/reset-password", json={"new_password": "short"}, headers=_auth(admin_token)
    )
    assert short.status_code == 422

    missing = await client.post(
        f"/api/v1/admin/users/{uuid.uuid4()}/reset-password",
        json={"new_password": "validpassword1"},
        headers=_auth(admin_token),
    )
    assert missing.status_code == 404


async def test_only_super_admin_can_edit_users_or_reset_passwords(client, db_session):
    target, _ = await _make_user(client, db_session, "target@example.com", "oldpassword1", "customer")
    _, ops_token = await _make_user(client, db_session, "ops@example.com", "supersecret1", "operations")
    _, cust_token = await _make_user(client, db_session, "cust@example.com", "supersecret1", "customer")

    for token in (ops_token, cust_token):
        edit = await client.patch(f"/api/v1/admin/users/{target.id}", json={"phone": "0700000000"}, headers=_auth(token))
        reset = await client.post(
            f"/api/v1/admin/users/{target.id}/reset-password",
            json={"new_password": "validpassword1"},
            headers=_auth(token),
        )
        assert edit.status_code == 403
        assert reset.status_code == 403

    anon = await client.post(f"/api/v1/admin/users/{target.id}/reset-password", json={"new_password": "validpassword1"})
    assert anon.status_code == 401
