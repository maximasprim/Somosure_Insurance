from sqlalchemy import select


async def test_registration_generates_referral_code_on_request(client, db_session):
    await client.post("/api/v1/auth/register", json={"full_name": "Referrer", "email": "referrer@example.com", "password": "supersecret1"})
    login = await client.post("/api/v1/auth/login", json={"email": "referrer@example.com", "password": "supersecret1"})
    token = login.json()["access_token"]

    res = await client.get("/api/v1/me/referral-code", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    code = res.json()["code"]
    assert code.startswith("SOM")
    assert res.json()["status"] == "pending"

    # Calling again should return the SAME code, not generate a new one.
    res2 = await client.get("/api/v1/me/referral-code", headers={"Authorization": f"Bearer {token}"})
    assert res2.json()["code"] == code


async def test_referral_code_redeemed_at_registration(client, db_session):
    from app.models.referral import Referral

    await client.post("/api/v1/auth/register", json={"full_name": "Referrer2", "email": "referrer2@example.com", "password": "supersecret1"})
    login = await client.post("/api/v1/auth/login", json={"email": "referrer2@example.com", "password": "supersecret1"})
    token = login.json()["access_token"]
    code = (await client.get("/api/v1/me/referral-code", headers={"Authorization": f"Bearer {token}"})).json()["code"]

    reg_res = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Referred Friend", "email": "referred@example.com", "password": "supersecret1", "referral_code": code},
    )
    assert reg_res.status_code == 201

    referral = await db_session.scalar(select(Referral).where(Referral.code == code))
    assert referral.referred_customer_id is not None
    assert referral.status == "pending"  # not converted until a policy issues


async def test_cannot_redeem_nonexistent_referral_code(client):
    res = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "No Code User", "email": "nocode@example.com", "password": "supersecret1", "referral_code": "SOMNOTREAL"},
    )
    # Registration should still succeed even with a bad code - a
    # non-existent code just means no referral link is created, it
    # shouldn't block the account from being created.
    assert res.status_code == 201


async def test_published_faq_visible_publicly(client, db_session):
    import uuid

    from app.models.content import Faq

    db_session.add(Faq(id=uuid.uuid4(), question="Is this covered?", answer="Yes.", is_published=True, display_order=1))
    db_session.add(Faq(id=uuid.uuid4(), question="Draft question", answer="Draft answer", is_published=False, display_order=2))
    await db_session.commit()

    res = await client.get("/api/v1/faqs")
    assert res.status_code == 200
    questions = [f["question"] for f in res.json()]
    assert "Is this covered?" in questions
    assert "Draft question" not in questions


async def test_unpublished_content_not_accessible_publicly(client, db_session):
    import uuid

    from app.models.content import Content

    db_session.add(Content(id=uuid.uuid4(), slug="draft-article", title="Draft", body="Not ready yet", is_published=False))
    await db_session.commit()

    res = await client.get("/api/v1/content/draft-article")
    assert res.status_code == 404
