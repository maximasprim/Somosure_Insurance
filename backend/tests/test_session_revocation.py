"""Signing users out everywhere (token versions) and forced password change."""

import uuid
from datetime import datetime, timedelta, timezone

from jose import jwt
from sqlalchemy import select


async def _make_user(client, db_session, email, password, role_name, full_name="Test User"):
    """Registers an account and moves it to `role_name` in the DB, then signs in.
    Returns (user, login_response_json)."""
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
    return user, login.json()


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def _me(client, token):
    return await client.get("/api/v1/me", headers=_auth(token))


async def test_deactivating_a_user_ends_their_open_sessions(client, db_session):
    _, admin = await _make_user(client, db_session, "boss@example.com", "supersecret1", "super_admin")
    target, session = await _make_user(client, db_session, "target@example.com", "supersecret1", "customer")
    assert (await _me(client, session["access_token"])).status_code == 200

    res = await client.patch(
        f"/api/v1/admin/users/{target.id}", json={"is_active": False}, headers=_auth(admin["access_token"])
    )
    assert res.status_code == 200

    assert (await _me(client, session["access_token"])).status_code == 401
    refresh = await client.post("/api/v1/auth/refresh", json={"refresh_token": session["refresh_token"]})
    assert refresh.status_code == 401

    # Re-activating does not resurrect the old session; signing in again works.
    await client.patch(f"/api/v1/admin/users/{target.id}", json={"is_active": True}, headers=_auth(admin["access_token"]))
    assert (await _me(client, session["access_token"])).status_code == 401
    login = await client.post("/api/v1/auth/login", json={"email": "target@example.com", "password": "supersecret1"})
    assert login.status_code == 200
    assert (await _me(client, login.json()["access_token"])).status_code == 200


async def test_admin_password_reset_signs_user_out_and_forces_a_change(client, db_session):
    _, admin = await _make_user(client, db_session, "boss@example.com", "supersecret1", "super_admin")
    target, session = await _make_user(client, db_session, "target@example.com", "oldpassword1", "customer")

    res = await client.post(
        f"/api/v1/admin/users/{target.id}/reset-password",
        json={"new_password": "temporarypass1"},
        headers=_auth(admin["access_token"]),
    )
    assert res.status_code == 204

    # The device that was signed in is out - access and refresh.
    assert (await _me(client, session["access_token"])).status_code == 401
    assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": session["refresh_token"]})).status_code == 401

    # Signing in with the temporary password works but is flagged.
    login = await client.post("/api/v1/auth/login", json={"email": "target@example.com", "password": "temporarypass1"})
    assert login.status_code == 200
    body = login.json()
    assert body["must_change_password"] is True
    assert jwt.get_unverified_claims(body["access_token"]).get("mcp") is True

    # Everything except changing the password is refused until they do.
    blocked = await _me(client, body["access_token"])
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "password_change_required"

    wrong = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "not-it-at-all", "new_password": "mychosenpass1"},
        headers=_auth(body["access_token"]),
    )
    assert wrong.status_code == 400

    same = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "temporarypass1", "new_password": "temporarypass1"},
        headers=_auth(body["access_token"]),
    )
    assert same.status_code == 400

    changed = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "temporarypass1", "new_password": "mychosenpass1"},
        headers=_auth(body["access_token"]),
    )
    assert changed.status_code == 200
    fresh = changed.json()
    assert fresh["must_change_password"] is False
    assert "mcp" not in jwt.get_unverified_claims(fresh["access_token"])

    # The new tokens work; the flagged ones from before the change do not.
    assert (await _me(client, fresh["access_token"])).status_code == 200
    assert (await _me(client, body["access_token"])).status_code == 401

    # And the new password is the one that signs in from now on.
    assert (await client.post("/api/v1/auth/login", json={"email": "target@example.com", "password": "temporarypass1"})).status_code == 401
    assert (await client.post("/api/v1/auth/login", json={"email": "target@example.com", "password": "mychosenpass1"})).status_code == 200


async def test_admin_can_reset_without_forcing_a_change(client, db_session):
    _, admin = await _make_user(client, db_session, "boss@example.com", "supersecret1", "super_admin")
    target, _ = await _make_user(client, db_session, "target@example.com", "oldpassword1", "customer")

    await client.post(
        f"/api/v1/admin/users/{target.id}/reset-password",
        json={"new_password": "temporarypass1", "require_password_change": False},
        headers=_auth(admin["access_token"]),
    )
    login = await client.post("/api/v1/auth/login", json={"email": "target@example.com", "password": "temporarypass1"})
    assert login.json()["must_change_password"] is False
    assert (await _me(client, login.json()["access_token"])).status_code == 200


async def test_new_staff_account_must_change_its_temporary_password(client, db_session):
    _, admin = await _make_user(client, db_session, "boss@example.com", "supersecret1", "super_admin")
    await _make_user(client, db_session, "agent@example.com", "supersecret1", "sales_agent")  # makes sure the role exists

    created = await client.post(
        "/api/v1/admin/users",
        json={"full_name": "New Staffer", "email": "newstaff@example.com", "password": "temporarypass1", "role": "sales_agent"},
        headers=_auth(admin["access_token"]),
    )
    assert created.status_code == 201
    assert created.json()["must_change_password"] is True

    login = await client.post("/api/v1/auth/login", json={"email": "newstaff@example.com", "password": "temporarypass1"})
    assert login.json()["must_change_password"] is True


async def test_changing_your_own_password_signs_out_your_other_devices(client, db_session):
    _, first = await _make_user(client, db_session, "person@example.com", "firstpassword1", "customer")
    second = (await client.post("/api/v1/auth/login", json={"email": "person@example.com", "password": "firstpassword1"})).json()

    changed = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "firstpassword1", "new_password": "secondpassword2"},
        headers=_auth(first["access_token"]),
    )
    assert changed.status_code == 200
    kept = changed.json()

    assert (await _me(client, second["access_token"])).status_code == 401
    assert (await _me(client, first["access_token"])).status_code == 401
    assert (await _me(client, kept["access_token"])).status_code == 200


async def test_resetting_via_the_email_link_ends_old_sessions_and_clears_a_forced_change(client, db_session):
    from app.core.security import generate_reset_token, hash_reset_token
    from app.models.password_reset_token import PasswordResetToken
    from app.models.user import User

    _, admin = await _make_user(client, db_session, "boss@example.com", "supersecret1", "super_admin")
    target, _ = await _make_user(client, db_session, "target@example.com", "oldpassword1", "customer")
    await client.post(
        f"/api/v1/admin/users/{target.id}/reset-password",
        json={"new_password": "temporarypass1"},
        headers=_auth(admin["access_token"]),
    )
    flagged = (await client.post("/api/v1/auth/login", json={"email": "target@example.com", "password": "temporarypass1"})).json()
    assert flagged["must_change_password"] is True

    raw = generate_reset_token()
    db_session.add(
        PasswordResetToken(
            user_id=target.id,
            token_hash=hash_reset_token(raw),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
    )
    await db_session.commit()

    res = await client.post("/api/v1/auth/reset-password", json={"token": raw, "new_password": "chosenbyuser1"})
    assert res.status_code == 204

    assert (await _me(client, flagged["access_token"])).status_code == 401
    db_session.expire_all()
    user = await db_session.scalar(select(User).where(User.id == target.id))
    assert user.must_change_password is False
    login = await client.post("/api/v1/auth/login", json={"email": "target@example.com", "password": "chosenbyuser1"})
    assert login.json()["must_change_password"] is False


async def test_changing_a_users_role_ends_their_old_sessions(client, db_session):
    _, admin = await _make_user(client, db_session, "boss@example.com", "supersecret1", "super_admin")
    await _make_user(client, db_session, "agent@example.com", "supersecret1", "sales_agent")
    target, session = await _make_user(client, db_session, "target@example.com", "supersecret1", "customer")

    # Same role again: nothing to revoke.
    same = await client.patch(f"/api/v1/admin/users/{target.id}", json={"role": "customer"}, headers=_auth(admin["access_token"]))
    assert same.status_code == 200
    assert (await _me(client, session["access_token"])).status_code == 200

    changed = await client.patch(
        f"/api/v1/admin/users/{target.id}", json={"role": "sales_agent"}, headers=_auth(admin["access_token"])
    )
    assert changed.status_code == 200
    assert (await _me(client, session["access_token"])).status_code == 401


async def test_editing_name_email_or_phone_does_not_sign_anyone_out(client, db_session):
    _, admin = await _make_user(client, db_session, "boss@example.com", "supersecret1", "super_admin")
    target, session = await _make_user(client, db_session, "target@example.com", "supersecret1", "customer")

    res = await client.patch(
        f"/api/v1/admin/users/{target.id}",
        json={"full_name": "Renamed Person", "phone": "0711000111"},
        headers=_auth(admin["access_token"]),
    )
    assert res.status_code == 200
    assert (await _me(client, session["access_token"])).status_code == 200


async def test_revoke_sessions_signs_out_but_keeps_the_password(client, db_session):
    _, admin = await _make_user(client, db_session, "boss@example.com", "supersecret1", "super_admin")
    target, session = await _make_user(client, db_session, "target@example.com", "supersecret1", "customer")

    res = await client.post(f"/api/v1/admin/users/{target.id}/revoke-sessions", headers=_auth(admin["access_token"]))
    assert res.status_code == 204
    assert (await _me(client, session["access_token"])).status_code == 401

    login = await client.post("/api/v1/auth/login", json={"email": "target@example.com", "password": "supersecret1"})
    assert login.status_code == 200
    assert login.json()["must_change_password"] is False


async def test_admin_cannot_reset_their_own_password_through_the_admin_endpoint(client, db_session):
    admin_user, admin = await _make_user(client, db_session, "boss@example.com", "supersecret1", "super_admin")

    res = await client.post(
        f"/api/v1/admin/users/{admin_user.id}/reset-password",
        json={"new_password": "anotherpass12"},
        headers=_auth(admin["access_token"]),
    )
    assert res.status_code == 400
    assert (await _me(client, admin["access_token"])).status_code == 200


async def test_only_super_admin_can_revoke_sessions(client, db_session):
    target, _ = await _make_user(client, db_session, "target@example.com", "supersecret1", "customer")
    _, ops = await _make_user(client, db_session, "ops@example.com", "supersecret1", "operations")

    res = await client.post(f"/api/v1/admin/users/{target.id}/revoke-sessions", headers=_auth(ops["access_token"]))
    assert res.status_code == 403
    assert (await client.post(f"/api/v1/admin/users/{target.id}/revoke-sessions")).status_code == 401


async def test_tokens_issued_before_versions_existed_keep_working(client, db_session):
    from datetime import timedelta as td

    from app.core.security import create_token
    from app.models.user import User

    _, session = await _make_user(client, db_session, "old@example.com", "supersecret1", "customer")
    user = await db_session.scalar(select(User).where(User.email == "old@example.com"))

    # A token minted by the previous release: no "tv" and no "mcp" claim.
    legacy = create_token(str(user.id), td(minutes=5), {"role": "customer", "type": "access"})
    assert (await _me(client, legacy)).status_code == 200


async def test_a_revoked_token_is_treated_as_a_guest_where_login_is_optional(client, db_session):
    """get_optional_customer_id (used by payments, applications, financing) must
    fall back to 'guest' for a dead token rather than recognise the customer."""
    from app.core.deps import get_optional_customer_id
    from app.models.user import User

    user, session = await _make_user(client, db_session, "gone@example.com", "supersecret1", "customer")
    assert await get_optional_customer_id(token=session["access_token"], db=db_session) is not None

    row = await db_session.scalar(select(User).where(User.id == user.id))
    row.token_version += 1
    await db_session.commit()

    assert await get_optional_customer_id(token=session["access_token"], db=db_session) is None
