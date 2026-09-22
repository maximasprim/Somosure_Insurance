"""Password reset flow: forgot-password (generic response, real dispatch
attempt via the notification registry) through reset-password (single-use,
expiring token). Mirrors the register/login pattern in tests/test_auth.py.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select


async def _register(client, email="reset@example.com", password="correcthorse1"):
    return await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Reset Test", "email": email, "password": password},
    )


async def test_forgot_password_returns_same_generic_message_regardless_of_email(client):
    await _register(client)

    known = await client.post("/api/v1/auth/forgot-password", json={"email": "reset@example.com"})
    unknown = await client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"})

    assert known.status_code == 200
    assert unknown.status_code == 200
    assert known.json()["message"] == unknown.json()["message"]


async def test_forgot_password_creates_a_hashed_single_use_token(client, db_session):
    from app.models.password_reset_token import PasswordResetToken
    from app.models.user import User

    await _register(client, email="hashcheck@example.com")
    await client.post("/api/v1/auth/forgot-password", json={"email": "hashcheck@example.com"})

    user = await db_session.scalar(select(User).where(User.email == "hashcheck@example.com"))
    token_row = await db_session.scalar(select(PasswordResetToken).where(PasswordResetToken.user_id == user.id))

    assert token_row is not None
    assert token_row.used_at is None
    assert token_row.expires_at > datetime.now(timezone.utc)
    # The raw token is never persisted - only a hash of it.
    assert token_row.token_hash != ""
    assert len(token_row.token_hash) == 64  # sha256 hex digest length


async def _issue_and_capture_raw_token(client, db_session, monkeypatch, email):
    """Forgot-password only exposes the raw token via the (mocked) email
    dispatch - capture it there instead of reaching into the DB, so this
    test exercises the same path a real user's email link would."""
    from app.notifications import registry

    captured = {}

    class _CapturingDispatcher:
        is_mock = True

        async def send_email(self, email, subject, body):
            captured["body"] = body
            from app.notifications.base import DispatchResult

            return DispatchResult(delivered=True, is_mock=True)

        async def send_sms(self, phone, body):
            raise NotImplementedError

    monkeypatch.setattr(registry, "get_dispatcher", lambda: _CapturingDispatcher())

    await client.post("/api/v1/auth/forgot-password", json={"email": email})
    reset_link = captured["body"].split("\n\n")[-2] if "\n\n" in captured["body"] else captured["body"]
    return reset_link.strip().split("token=")[-1]


async def test_reset_password_with_valid_token_lets_user_log_in_with_new_password(client, db_session, monkeypatch):
    await _register(client, email="fullflow@example.com", password="oldpassword1")
    raw_token = await _issue_and_capture_raw_token(client, db_session, monkeypatch, "fullflow@example.com")

    reset_res = await client.post(
        "/api/v1/auth/reset-password", json={"token": raw_token, "new_password": "newpassword1"}
    )
    assert reset_res.status_code == 204

    old_login = await client.post("/api/v1/auth/login", json={"email": "fullflow@example.com", "password": "oldpassword1"})
    assert old_login.status_code == 401

    new_login = await client.post("/api/v1/auth/login", json={"email": "fullflow@example.com", "password": "newpassword1"})
    assert new_login.status_code == 200


async def test_reset_token_cannot_be_reused(client, db_session, monkeypatch):
    await _register(client, email="reuse@example.com", password="oldpassword1")
    raw_token = await _issue_and_capture_raw_token(client, db_session, monkeypatch, "reuse@example.com")

    first = await client.post("/api/v1/auth/reset-password", json={"token": raw_token, "new_password": "newpassword1"})
    assert first.status_code == 204

    second = await client.post("/api/v1/auth/reset-password", json={"token": raw_token, "new_password": "anotherpassword1"})
    assert second.status_code == 400


async def test_expired_reset_token_is_rejected(client, db_session, monkeypatch):
    from app.models.password_reset_token import PasswordResetToken
    from app.models.user import User

    await _register(client, email="expired@example.com")
    raw_token = await _issue_and_capture_raw_token(client, db_session, monkeypatch, "expired@example.com")

    user = await db_session.scalar(select(User).where(User.email == "expired@example.com"))
    token_row = await db_session.scalar(select(PasswordResetToken).where(PasswordResetToken.user_id == user.id))
    token_row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    await db_session.commit()

    res = await client.post("/api/v1/auth/reset-password", json={"token": raw_token, "new_password": "newpassword1"})
    assert res.status_code == 400


async def test_reset_password_with_garbage_token_returns_400_not_500(client):
    res = await client.post("/api/v1/auth/reset-password", json={"token": "not-a-real-token", "new_password": "newpassword1"})
    assert res.status_code == 400
