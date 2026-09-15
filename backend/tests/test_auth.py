import pytest


async def test_register_creates_user_and_customer_record(client, db_session):
    from sqlalchemy import select

    from app.models.customer import Customer

    res = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Jane Wanjiru", "email": "jane@example.com", "phone": "0712345678", "password": "supersecret1"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["email"] == "jane@example.com"

    # The register endpoint should have created a linked Customer row too -
    # this is the fix that closed the Phase 4 guest-flow gap.
    customer = await db_session.scalar(select(Customer).where(Customer.email == "jane@example.com"))
    assert customer is not None
    assert customer.phone == "0712345678"


async def test_duplicate_registration_rejected(client):
    payload = {"full_name": "Dup User", "email": "dup@example.com", "password": "supersecret1"}
    first = await client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201

    second = await client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409


async def test_login_success_and_wrong_password(client):
    await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Login Test", "email": "login@example.com", "password": "correcthorse1"},
    )

    good = await client.post("/api/v1/auth/login", json={"email": "login@example.com", "password": "correcthorse1"})
    assert good.status_code == 200
    tokens = good.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    bad = await client.post("/api/v1/auth/login", json={"email": "login@example.com", "password": "wrongpassword"})
    assert bad.status_code == 401


async def test_login_nonexistent_user_returns_401_not_500(client):
    res = await client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever123"})
    assert res.status_code == 401


async def test_refresh_token_issues_new_access_token(client):
    await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Refresh Test", "email": "refresh@example.com", "password": "correcthorse1"},
    )
    login_res = await client.post("/api/v1/auth/login", json={"email": "refresh@example.com", "password": "correcthorse1"})
    refresh_token = login_res.json()["refresh_token"]

    refreshed = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refreshed.status_code == 200
    assert "access_token" in refreshed.json()
